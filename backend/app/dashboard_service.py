from app.dashboard_repository import DashboardRepository


def get_dashboard_stats(
    business_id: str,
):
    repo = DashboardRepository()

    return repo.get_stats(
        business_id
    )