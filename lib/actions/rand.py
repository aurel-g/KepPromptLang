from typing import List

import torch
from torch.nn import Embedding

from custom_nodes.KepPromptLang.lib.action.base import (
    Action,
    MultiArgAction,
)
from custom_nodes.KepPromptLang.lib.actions.types import SegOrAction
from custom_nodes.KepPromptLang.lib.parser.prompt_segment import PromptSegment


class RandAction(Action):
    grammar = 'rand(" arg ")"'
    name = "rand"
    chars = None

    parsed_token_length = 0
    range_min = 0
    range_max = 1

    def __init__(self, args: List[List[SegOrAction]]) -> None:
        self.args = args
        if len(args) != 1 and len(args) != 3:
            raise ValueError("Random action should have exactly one argument or three arguments")

        self._parse_token_length(args[0])

        if len(args) == 3:
            self._parse_range(args[1], args[2])

    def _parse_token_length(self, arg: List[SegOrAction]) -> None:
        if len(arg) != 1:
            raise ValueError("Random action first argument should have exactly one segment")

        token_length_seg_or_action = arg[0]

        if isinstance(token_length_seg_or_action, Action):
            raise ValueError("Random action should not have an action as an argument")

        try:
            self.parsed_token_length = int(token_length_seg_or_action.text)
        except ValueError:
            raise ValueError("Random action should have an integer as the first argument")

    def _parse_range(self, min_arg: List[SegOrAction], max_arg: List[SegOrAction]) -> None:
        if len(min_arg) != 1:
            raise ValueError("Random action second argument should have exactly one segment")

        if len(max_arg) != 1:
            raise ValueError("Random action third argument should have exactly one segment")

        min_seg_or_action = min_arg[0]
        max_seg_or_action = max_arg[0]

        if isinstance(min_seg_or_action, Action):
            raise ValueError("Random action should not have an action as an argument")

        if isinstance(max_seg_or_action, Action):
            raise ValueError("Random action should not have an action as an argument")

        try:
            self.range_min = int(min_seg_or_action.text)
        except ValueError:
            raise ValueError("Random action should have an integer as the second argument")

        try:
            self.range_max = int(max_seg_or_action.text)
        except ValueError:
            raise ValueError("Random action should have an integer as the third argument")

        if self.range_min > self.range_max:
            raise ValueError("Random action should have the second argument be less than the third argument")
    def token_length(self) -> int:
        """
        Random returns a random embedding whose length is the number in the argument
        :return:
        """
        return self.parsed_token_length

    def get_result(self, embedding_module: Embedding) -> torch.Tensor:
        # Create random tensor of size
        result = torch.empty(1, self.parsed_token_length, embedding_module.embedding_dim).uniform_(self.range_min, self.range_max)
        return result

    def get_all_segments(self) -> List[PromptSegment]:
        segments = []
        for arg in self.args:
            for seg_or_action in arg:
                if isinstance(seg_or_action, Action):
                    segments.extend(seg_or_action.get_all_segments())
                else:
                    segments.append(seg_or_action)

        return segments
