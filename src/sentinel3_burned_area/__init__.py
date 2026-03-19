__all__ = ["MonthOutputs", "ProcessRunResult", "process_month", "process_range"]


def __getattr__(name: str):
    if name in {"MonthOutputs", "ProcessRunResult"}:
        from sentinel3_burned_area.models import MonthOutputs, ProcessRunResult

        return {"MonthOutputs": MonthOutputs, "ProcessRunResult": ProcessRunResult}[name]
    if name in {"process_month", "process_range"}:
        from sentinel3_burned_area.processing import process_month, process_range

        return {"process_month": process_month, "process_range": process_range}[name]
    raise AttributeError(f"module 'sentinel3_burned_area' has no attribute {name!r}")
