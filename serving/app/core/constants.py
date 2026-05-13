from enum import Enum


class SGrade(str, Enum):
    """
    성장 S등급 (S1~S10) 정의.
    S1이 가장 높은 등급, S10이 가장 낮은 등급.
    SCB 점수(CB 점수 + S등급 가산점)와 혼용 금지.
    """

    S1 = "S1"
    S2 = "S2"
    S3 = "S3"
    S4 = "S4"
    S5 = "S5"
    S6 = "S6"
    S7 = "S7"
    S8 = "S8"
    S9 = "S9"
    S10 = "S10"

    @classmethod
    def from_index(cls, index: int) -> "SGrade":
        """
        모델 출력 인덱스(0~9)를 S등급으로 변환.
        index 0 → S1, index 9 → S10
        """
        members = list(cls)
        if not (0 <= index < len(members)):
            raise ValueError(f"유효하지 않은 S등급 인덱스: {index} (0~9 범위여야 합니다)")
        return members[index]
