"""
Сервис для управления расходами (CRUD операции)
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import List, Optional
from datetime import datetime
from models.expense import Expense
from models.transaction import Transaction
from models.account import Account
from schemas.expenses_management import (
    CreateExpenseRequest,
    ExpenseItem,
    ExpensesListResponse,
    ExpenseDetailResponse,
    UpdateExpenseRequest,
)
import logging

logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> datetime:
    """Парсинг даты из строки DD.MM.YYYY или ISO формата"""
    try:
        # Пробуем формат DD.MM.YYYY
        if "." in date_str and len(date_str.split(".")) == 3:
            return datetime.strptime(date_str, "%d.%m.%Y")
        # Пробуем ISO формат
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception as e:
        logger.error(f"Ошибка парсинга даты {date_str}: {e}")
        raise ValueError(f"Неверный формат даты: {date_str}")


def format_date(dt: datetime) -> str:
    """Форматирование даты в ISO формат"""
    return dt.isoformat()


def _create_transaction_for_expense(db: Session, expense: Expense) -> None:
    """Создать транзакцию для расхода"""
    try:
        # Ищем счет для расхода
        account = None
        if expense.account_id:
            account = db.query(Account).filter(
                Account.iiko_id == expense.account_id,
                Account.deleted == False
            ).first()
        
        # Если счет не указан или не найден, ищем счет типа EXPENSES
        if not account:
            account = db.query(Account).filter(
                Account.type == "EXPENSES",
                Account.deleted == False
            ).first()
        
        if not account:
            logger.warning(f"Не найден счет типа EXPENSES для создания транзакции расхода {expense.id}")
            return
        
        # Создаем транзакцию
        transaction = Transaction(
            amount=float(expense.amount),
            amount_in=0,
            amount_out=float(expense.amount),
            transaction_side="Кредит",
            transaction_type="EXPENSES",
            account_id=account.iiko_id,
            account_name=account.name,
            account_type=account.type,
            date_typed=expense.date,
            date_time_typed=expense.date,
            organization_id=expense.organization_id,
            comment=f"Расход ({expense.expense_type}): {expense.comment or ''}",
        )
        
        db.add(transaction)
        db.commit()
        logger.debug(f"Создана транзакция для расхода {expense.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания транзакции для расхода {expense.id}: {e}")
        raise


def create_expense(
    db: Session,
    expense_data: CreateExpenseRequest,
    user_id: Optional[int] = None,
) -> Expense:
    """Создать новый расход"""
    try:
        expense_date = parse_date(expense_data.date)
        
        expense = Expense(
            organization_id=expense_data.organization_id,
            expense_type=expense_data.expense_type,
            amount=expense_data.amount,
            date=expense_date,
            comment=expense_data.comment,
            account_id=expense_data.account_id,
            created_by=user_id,
        )
        
        db.add(expense)
        db.commit()
        db.refresh(expense)
        
        # Создаем транзакцию для расхода
        try:
            _create_transaction_for_expense(db, expense)
        except Exception as trans_err:
            logger.warning(f"Не удалось создать транзакцию для расхода {expense.id}: {trans_err}")
            # Не прерываем выполнение, расход уже создан
        
        logger.info(f"Создан расход ID={expense.id}, тип={expense_data.expense_type}, сумма={expense_data.amount}")
        return expense
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка создания расхода: {e}")
        raise


def get_expenses(
    db: Session,
    organization_id: Optional[int] = None,
    expense_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> ExpensesListResponse:
    """Получить список расходов с фильтрацией"""
    try:
        query = db.query(Expense)
        
        # Фильтры
        if organization_id:
            query = query.filter(Expense.organization_id == organization_id)
        if expense_type:
            query = query.filter(Expense.expense_type == expense_type)
        if from_date:
            from_dt = parse_date(from_date)
            query = query.filter(Expense.date >= from_dt)
        if to_date:
            to_dt = parse_date(to_date)
            # Добавляем время конца дня
            to_dt = to_dt.replace(hour=23, minute=59, second=59)
            query = query.filter(Expense.date <= to_dt)
        
        # Общая сумма
        total_amount = float(query.with_entities(func.sum(Expense.amount)).scalar() or 0)
        
        # Сортировка и пагинация
        expenses = query.order_by(Expense.date.desc()).offset(offset).limit(limit).all()
        
        expense_items = [
            ExpenseItem(
                id=exp.id,
                organization_id=exp.organization_id,
                expense_type=exp.expense_type,
                amount=float(exp.amount),
                date=format_date(exp.date),
                comment=exp.comment,
                account_id=exp.account_id,
                created_by=exp.created_by,
                created_at=format_date(exp.created_at),
                updated_at=format_date(exp.updated_at),
            )
            for exp in expenses
        ]
        
        return ExpensesListResponse(
            success=True,
            message=f"Найдено расходов: {len(expense_items)}",
            expenses=expense_items,
            total=total_amount,
        )
    except Exception as e:
        logger.error(f"Ошибка получения списка расходов: {e}")
        raise


def get_expense_by_id(
    db: Session,
    expense_id: int,
) -> Optional[ExpenseDetailResponse]:
    """Получить расход по ID"""
    try:
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        
        if not expense:
            return None
        
        expense_item = ExpenseItem(
            id=expense.id,
            organization_id=expense.organization_id,
            expense_type=expense.expense_type,
            amount=float(expense.amount),
            date=format_date(expense.date),
            comment=expense.comment,
            account_id=expense.account_id,
            created_by=expense.created_by,
            created_at=format_date(expense.created_at),
            updated_at=format_date(expense.updated_at),
        )
        
        return ExpenseDetailResponse(
            success=True,
            message="Расход найден",
            expense=expense_item,
        )
    except Exception as e:
        logger.error(f"Ошибка получения расхода ID={expense_id}: {e}")
        raise


def update_expense(
    db: Session,
    expense_id: int,
    expense_data: UpdateExpenseRequest,
) -> Expense:
    """Обновить расход"""
    try:
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        
        if not expense:
            raise ValueError(f"Расход с ID={expense_id} не найден")
        
        # Обновляем поля
        if expense_data.expense_type is not None:
            expense.expense_type = expense_data.expense_type
        if expense_data.amount is not None:
            expense.amount = expense_data.amount
        if expense_data.date is not None:
            expense.date = parse_date(expense_data.date)
        if expense_data.comment is not None:
            expense.comment = expense_data.comment
        if expense_data.account_id is not None:
            expense.account_id = expense_data.account_id
        
        expense.updated_at = datetime.now()
        
        db.commit()
        db.refresh(expense)
        
        logger.info(f"Обновлен расход ID={expense_id}")
        return expense
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления расхода ID={expense_id}: {e}")
        raise


def delete_expense(
    db: Session,
    expense_id: int,
) -> bool:
    """Удалить расход"""
    try:
        expense = db.query(Expense).filter(Expense.id == expense_id).first()
        
        if not expense:
            raise ValueError(f"Расход с ID={expense_id} не найден")
        
        db.delete(expense)
        db.commit()
        
        logger.info(f"Удален расход ID={expense_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка удаления расхода ID={expense_id}: {e}")
        raise

