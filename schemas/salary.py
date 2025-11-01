from pydantic import BaseModel
from typing import List, Optional
from schemas.quests import QuestResponse


class BonusItem(BaseModel):
    """Элемент бонуса"""
    type: str
    amount: float
    description: str


class PenaltyItem(BaseModel):
    """Элемент штрафа"""
    reason: str
    amount: float
    date: str


class QuestRewardItem(BaseModel):
    """Элемент награды за квест"""
    questId: str
    questName: str
    reward: float


class SalaryBreakdown(BaseModel):
    """Детализация зарплаты"""
    baseSalary: float
    percentage: float
    bonuses: List[BonusItem]
    penalties: List[PenaltyItem]
    questRewards: List[QuestRewardItem]


class SalaryResponse(BaseModel):
    """Ответ с информацией о зарплате официанта"""
    date: str  # "DD.MM.YYYY"
    tablesCompleted: int
    totalRevenue: float
    salary: float
    salaryPercentage: float  # Процент от выручки
    bonuses: float
    questBonus: float
    questDescription: str  # Описание квеста, за который получен бонус
    penalties: float
    totalEarnings: float
    breakdown: SalaryBreakdown
    quests: List[QuestResponse]  # Список квестов на этот день

    class Config:
        from_attributes = True

