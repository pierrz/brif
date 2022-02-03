# pylint: disable=too-few-public-methods

"""
Module gathering all data models
"""

from typing import Optional

from pydantic import BaseModel


class Dataset(BaseModel):
    fullname: str
    dir_name: str
    mapping: str
    total: int = 0
    valid: Optional[int]
    valid_img: Optional[int]
    status: str

    def field_list(self):
        return list(self.__fields__.keys())


class InputDataset(Dataset):
    status: str = "unprocessed"


def dataset_from_dict(data_dict):
    dataset = Dataset(
        fullname=data_dict["fullname"],
        dir_name=data_dict["dir_name"],
        mapping=data_dict["mapping"],
        total=data_dict["total"],
        valid=data_dict["valid"],
        valid_img=data_dict["valid_img"],
        status=data_dict["status"],
    )
    return dataset
