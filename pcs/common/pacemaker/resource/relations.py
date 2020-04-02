from dataclasses import dataclass
from typing import (
    Any,
    Mapping,
    Sequence,
    Union,
)

from pcs.common.types import ResourceRelationType
from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class RelationEntityDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    type: Union[ResourceRelationType, str]
    members: Sequence[str]
    metadata: Mapping[str, Any]


@dataclass(frozen=True)
class ResourceRelationDto(DataTransferObject):
    relation_entity: RelationEntityDto
    members: Sequence["ResourceRelationDto"]
    is_leaf: bool
