"""API routes for price related queries.

Currently exposes a single endpoint that fetches pricing data for
necessities from the Taiwan Executive Yuan open data portal.  If you
extend this domain with more features, consider adding schemas,
service modules and dependencies analogous to other domain packages.
"""

from fastapi import APIRouter, Query
import requests


router = APIRouter()


@router.get("/necessities-price")
def get_necessities_prices(category: str | None = Query(None), commodity: str | None = Query(None)):
    """Return pricing information for necessities from the open data API.

    :param category: Name of the category to filter by
    :param commodity: Name of the commodity to filter by
    """
    response = requests.get(
        "https://opendata.ey.gov.tw/api/ConsumerProtection/NecessitiesPrice",
        params={"CategoryName": category, "Name": commodity},
    )
    return response.json()
