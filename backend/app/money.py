"""Money is stored as integer pence, GBP only."""


def format_pence(pence: int) -> str:
    pounds, rem = divmod(pence, 100)
    return f"£{pounds}" if rem == 0 else f"£{pounds}.{rem:02d}"


def format_budget(budget_min: int, budget_max: int) -> str:
    return f"{format_pence(budget_min)} to {format_pence(budget_max)}"
