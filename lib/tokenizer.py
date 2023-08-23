import re
from typing import Union

from comfy.sd1_clip import SD1Tokenizer
from custom_nodes.ClipStuff.lib.actions import (
    NudgeAction,
    ArithAction,
    ALL_START_CHARS,
    ALL_END_CHARS,
    ALL_ACTIONS,
)
from custom_nodes.ClipStuff.lib.actions.base import (
    Action,
    PromptSegment,
    build_prompt_segment,
)
from custom_nodes.ClipStuff.lib.actions.lib import (
    is_any_action_segment,
    is_action_segment,
)
from custom_nodes.ClipStuff.lib.actions.utils import batch_size_info

arith_action = r'(<[a-zA-Z0-9\-_]+:[a-zA-Z0-9\-_]+>)'

# TODO: Get embedding identifier from tokenizer
tokenizer_regex = re.compile(
    fr"""
    \d+\.\d+                  # Capture decimals
    |
    (?:(?!embedding:)[\w\s]|embedding:[a-zA-Z0-9_]+)+ # Capture sequences of characters, including "embedding:"
    |
    \d+                       # Capture whole numbers
    |
    [:+-{re.escape("".join(ALL_START_CHARS))}{re.escape("".join(ALL_END_CHARS))}] # Capture special characters including start and end characters
    """,
    re.VERBOSE
)
def tokenize(text: str) -> list[str]:
    # Captures:
    # 1. Words
    # 2. Numbers(1.0, 1)
    # 3. Special characters(ALL_START_CHARS, ALL_END_CHARS, :, +, -)
    tokens = re.findall(tokenizer_regex, text)
    print(tokens)
    return [token.strip() for token in tokens]



def parse_segment(tokens: list[str], tokenizer: SD1Tokenizer) -> PromptSegment | Action:
    print("Parse segment: Checking token: " + tokens[0])
    for action in ALL_ACTIONS:
        if tokens[0] == action.START_CHAR:
            return action.parse_segment(tokens, ALL_START_CHARS, ALL_END_CHARS, parse_segment, tokenizer)
    # If we get here, it's a text segment
    return build_prompt_segment(tokens.pop(0), tokenizer)

def parse(tokens: list[str], tokenizer: SD1Tokenizer) -> list[PromptSegment | Action]:
    parsed = []
    while tokens:
        if tokens[0] == '':
            tokens.pop(0)
            continue
        print("Parse: Checking token: " + tokens[0])
        if tokens[0] in ALL_START_CHARS:
            parsed.append(parse_segment(tokens, tokenizer))
        else:
            parsed.append(build_prompt_segment(tokens.pop(0), tokenizer))
    return parsed


def parse_special_tokens(string) -> list[str]:
    out = []
    current = ""

    for char in string:
        if char in ALL_START_CHARS:
            out += [current]
            current = char
        elif char in ALL_END_CHARS:
            out += [current + char]
            current = ""
        else:
            current += char
    out += [current]
    return out


def parse_segment_actions(string, tokenizer: SD1Tokenizer) -> list[PromptSegment | NudgeAction | ArithAction]:
    tokens = tokenize(string)
    parsed = parse(tokens, tokenizer)
    return parsed

class TokenDict:
    def __init__(self,
                 token_id: int,
                 weight: float = None,
                 nudge_id=None, nudge_weight=None, nudge_start: int = None, nudge_end: int = None,
                 arith_ops: dict[str, list[str]] = None):
        if weight is None:
            self.weight = 1.0
        else:
            self.weight = weight

        self.token_id = token_id
        self.nudge_id = nudge_id
        self.nudge_weight = nudge_weight
        self.nudge_index_start = nudge_start
        self.nudge_index_stop = nudge_end

        self.arith_ops = arith_ops


class MyTokenizer(SD1Tokenizer):
    def __init__(self, tokenizer_path=None, max_length=77, pad_with_end=True, embedding_directory=None, embedding_size=768, embedding_key='clip_l', special_tokens=None):
        super().__init__(tokenizer_path, max_length, pad_with_end, embedding_directory, embedding_size, embedding_key)

    """
    Doesn't actually tokenize...
    Returns batches of segments and actions
    :return: List of list(batches) of segments and actions
    """
    def tokenize_with_weights(self, text:str, return_word_ids=False, **kwargs) -> list[list[PromptSegment | Action]]:
        if self.pad_with_end:
            pad_token = self.end_token
        else:
            pad_token = 0

        parsed_actions = parse_segment_actions(text, self)

        # nudge_start = kwargs.get("nudge_start")
        # nudge_end = kwargs.get("nudge_end")
        #
        # if nudge_start is not None and nudge_end is not None:
        #     nudge_start = int(nudge_start)
        #     nudge_end = int(nudge_end)
        #
        # # tokenize words
        for segment in parsed_actions:
            if isinstance(segment, Action):
                print(segment.depth_repr())
            else:
                print(segment.depth_repr())

        # reshape token array to CLIP input size
        batched_segments = []
        batch = [PromptSegment(text="[SOT]", tokens=[self.start_token])]
        # batched_segments.append(batch)
        batch_size = 1
        for segment in parsed_actions:
            num_tokens = segment.token_length()
            # determine if we're going to try and keep the tokens in a single batch
            is_large = num_tokens >= self.max_word_length

            # If the segment is too large to fit in a single batch, pad the current batch and start a new one
            if num_tokens + batch_size > self.max_length - 1:
                remaining_length = self.max_length - batch_size - 1 # -1 for end token
                # Pad batch
                batch.append(PromptSegment("__PAD__", [self.end_token] + [pad_token] * remaining_length - 1))
                batched_segments.append(batch)

                # start new batch
                batch = [PromptSegment(text="[SOT]", tokens=[self.start_token]), segment]
                batch_size = num_tokens + 1 # +1 for start token
                continue

            # If the segment is small enough to fit in the current batch, add it
            batch.append(segment)
            batch_size += num_tokens

        # Pad the last batch
        remaining_length = self.max_length - batch_size - 1 # -1 for end token
        batch.append(PromptSegment("__PAD__", [self.end_token] + [pad_token] * remaining_length))
        batched_segments.append(batch)

        for batch in batched_segments:
            batch_size_info(batch)

        return batched_segments
