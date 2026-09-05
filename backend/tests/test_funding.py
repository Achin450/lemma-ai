"""
Unit Tests for University Research Publishing Incentives & Grants Directory
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.funding_service import FundingService, VERIFIED_UNIVERSITY_BOUNTIES
from app.schemas.funding import FundingFilterParams

client = TestClient(app)


def test_minimum_amount_threshold():
    """Verify that every single university in the registry satisfies >= ₹10,000 threshold."""
    assert len(VERIFIED_UNIVERSITY_BOUNTIES) >= 15
    for u in VERIFIED_UNIVERSITY_BOUNTIES:
        assert u["min_amount_inr"] >= 10000, f"{u['name']} has min_amount_inr < 10000"
        assert u["max_amount_inr"] >= 10000, f"{u['name']} has max_amount_inr < 10000"
        for tier in u["reward_tiers"]:
            assert tier["amount_inr"] >= 10000, f"{u['name']} has tier {tier['tier_name']} < 10000"


def test_funding_service_all_universities():
    """Test default listing returns all universities sorted by max bounty descending."""
    results = FundingService.get_all_universities()
    assert len(results) >= 15
    # Verify sorted descending
    for i in range(len(results) - 1):
        assert results[i].max_amount_inr >= results[i + 1].max_amount_inr


def test_funding_service_region_filter():
    """Test filtering by India and International regions."""
    india_res = FundingService.get_all_universities(FundingFilterParams(region="India"))
    assert len(india_res) >= 8
    for u in india_res:
        assert u.region == "India"
        assert u.country == "India"

    foreign_res = FundingService.get_all_universities(FundingFilterParams(region="International"))
    assert len(foreign_res) >= 6
    for u in foreign_res:
        assert u.region == "International"
        assert u.country != "India"


def test_funding_service_search():
    """Test keyword search functionality."""
    res = FundingService.get_all_universities(FundingFilterParams(search_query="Chandigarh"))
    assert len(res) == 1
    assert res[0].short_name == "CU"

    res_saudi = FundingService.get_all_universities(FundingFilterParams(search_query="Saudi"))
    assert len(res_saudi) >= 2


def test_funding_service_summary_stats():
    """Test calculation of summary metrics."""
    stats = FundingService.get_summary_stats()
    assert stats.total_institutions >= 15
    assert stats.indian_institutions >= 8
    assert stats.foreign_institutions >= 6
    assert stats.max_bounty_inr >= 500000
    assert stats.max_bounty_usd >= 6000
    assert stats.min_threshold_inr == 10000


def test_api_list_universities():
    """Test GET /api/v1/funding/universities endpoint."""
    response = client.get("/api/v1/funding/universities")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 15
    assert "reward_tiers" in data[0]


def test_api_stats():
    """Test GET /api/v1/funding/stats endpoint."""
    response = client.get("/api/v1/funding/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["min_threshold_inr"] == 10000
    assert data["total_institutions"] >= 15


def test_api_university_detail():
    """Test GET /api/v1/funding/{id} endpoint."""
    response = client.get("/api/v1/funding/chandigarh-university")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Chandigarh University"
    assert len(data["reward_tiers"]) >= 4

    # 404 test
    not_found = client.get("/api/v1/funding/non-existent-uni")
    assert not_found.status_code == 404
