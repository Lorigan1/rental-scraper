"""Tests for the description parser using real-world listing snippets."""

import pytest
from rental_scraper.description_parser import DescriptionParser


class TestGenderPreference:
    def test_female_only(self):
        assert DescriptionParser.extract_gender_preference("Female only, clean and tidy") == "female_only"

    def test_female_only_with_no_couples(self):
        # When both "female only" and "no couples" appear, no_couples takes precedence
        assert DescriptionParser.extract_gender_preference("Female only, no couples") == "no_couples"

    def test_female_preferred(self):
        assert DescriptionParser.extract_gender_preference("Women preferred, clean and quiet") == "female_only"

    def test_male_only(self):
        assert DescriptionParser.extract_gender_preference("Male only, working professional") == "male_only"

    def test_couples_welcome(self):
        assert DescriptionParser.extract_gender_preference("Couples welcome! Great space") == "couples_welcome"

    def test_no_couples(self):
        assert DescriptionParser.extract_gender_preference("Sorry no couples, single occupant only") == "no_couples"

    def test_no_couples_before_couples_welcome(self):
        # "no couples" should take precedence
        assert DescriptionParser.extract_gender_preference("No couples allowed") == "no_couples"

    def test_for_a_female(self):
        assert DescriptionParser.extract_gender_preference("Room for a female in shared house") == "female_only"

    def test_no_gender_signal(self):
        assert DescriptionParser.extract_gender_preference("Nice room near downtown, parking included") is None


class TestLeaseType:
    def test_month_to_month(self):
        assert DescriptionParser.extract_lease_type("Month-to-month, flexible lease") == "month_to_month"

    def test_m2m(self):
        assert DescriptionParser.extract_lease_type("Available immediately, m2m rental") == "month_to_month"

    def test_no_lease(self):
        assert DescriptionParser.extract_lease_type("No lease required") == "month_to_month"

    def test_fixed_term(self):
        assert DescriptionParser.extract_lease_type("Minimum 6 months commitment") == "fixed_term"

    def test_one_year_lease(self):
        assert DescriptionParser.extract_lease_type("One-year lease required") == "fixed_term"

    def test_lease_agreement(self):
        assert DescriptionParser.extract_lease_type("Lease agreement required, references needed") == "fixed_term"

    def test_no_signal(self):
        assert DescriptionParser.extract_lease_type("Beautiful room for rent in Vancouver") is None


class TestMinLeaseMonths:
    def test_6_month_minimum(self):
        assert DescriptionParser.extract_min_lease_months("6 month minimum lease") == 6

    def test_minimum_3_months(self):
        assert DescriptionParser.extract_min_lease_months("Minimum 3 months stay") == 3

    def test_12_month_lease(self):
        assert DescriptionParser.extract_min_lease_months("12 month lease required") == 12

    def test_1_year_minimum(self):
        assert DescriptionParser.extract_min_lease_months("1 year minimum commitment") == 12

    def test_no_signal(self):
        assert DescriptionParser.extract_min_lease_months("Great room, available now") is None

    def test_unreasonable_value_rejected(self):
        assert DescriptionParser.extract_min_lease_months("100 month minimum") is None


class TestBathroomType:
    def test_private_bathroom(self):
        assert DescriptionParser.extract_bathroom_type("Private bathroom, own entrance") == "private"

    def test_ensuite(self):
        assert DescriptionParser.extract_bathroom_type("Ensuite bathroom included") == "private"

    def test_en_suite(self):
        assert DescriptionParser.extract_bathroom_type("Room with en-suite bath") == "private"

    def test_own_bathroom(self):
        assert DescriptionParser.extract_bathroom_type("Your own bathroom, separate from others") == "private"

    def test_shared_bathroom(self):
        assert DescriptionParser.extract_bathroom_type("Shared bathroom with one other person") == "shared"

    def test_common_washroom(self):
        assert DescriptionParser.extract_bathroom_type("Communal washroom on the same floor") == "shared"

    def test_no_signal(self):
        assert DescriptionParser.extract_bathroom_type("Room for rent, utilities included") is None


class TestLaundryType:
    def test_in_unit(self):
        assert DescriptionParser.extract_laundry_type("Washer/dryer in unit") == "in_unit"

    def test_laundry_in_suite(self):
        assert DescriptionParser.extract_laundry_type("Laundry in suite, dishwasher too") == "in_unit"

    def test_in_building(self):
        assert DescriptionParser.extract_laundry_type("Shared laundry in building") == "in_building"

    def test_coin_laundry(self):
        assert DescriptionParser.extract_laundry_type("Coin laundry downstairs") == "in_building"

    def test_laundry_on_site(self):
        assert DescriptionParser.extract_laundry_type("Laundry facilities available on-site") == "in_building"

    def test_no_signal(self):
        assert DescriptionParser.extract_laundry_type("Nice clean room, furnished") is None


class TestTransitProximity:
    def test_near_skytrain(self):
        assert DescriptionParser.extract_transit_proximity("Walking distance to SkyTrain") == "near_skytrain"

    def test_close_to_skytrain(self):
        assert DescriptionParser.extract_transit_proximity("Close to the skytrain station") == "near_skytrain"

    def test_steps_from_skytrain(self):
        assert DescriptionParser.extract_transit_proximity("Steps from SkyTrain, very convenient") == "near_skytrain"

    def test_near_commercial_broadway_station(self):
        assert DescriptionParser.extract_transit_proximity(
            "Near Commercial-Broadway station skytrain"
        ) == "near_skytrain"

    def test_near_bus(self):
        assert DescriptionParser.extract_transit_proximity("Close to bus stop, route 99") == "near_bus"

    def test_on_bus_route(self):
        assert DescriptionParser.extract_transit_proximity("Located on a bus route") == "near_bus"

    def test_good_transit(self):
        assert DescriptionParser.extract_transit_proximity("Excellent transit access") == "good_transit"

    def test_convenient_transportation(self):
        assert DescriptionParser.extract_transit_proximity("Convenient public transit nearby") == "good_transit"

    def test_no_signal(self):
        assert DescriptionParser.extract_transit_proximity("Quiet residential area, lots of parking") is None


class TestTransitDescription:
    def test_minutes_to_skytrain(self):
        desc = DescriptionParser.extract_transit_description("5 min walk to Commercial-Broadway SkyTrain station")
        assert desc is not None
        assert "commercial" in desc.lower()

    def test_blocks_from_station(self):
        desc = DescriptionParser.extract_transit_description("3 blocks from Joyce-Collingwood SkyTrain")
        assert desc is not None
        assert "joyce" in desc.lower()

    def test_no_signal(self):
        assert DescriptionParser.extract_transit_description("Great location, lots of amenities") is None


class TestFurnitureLevel:
    def test_fully_furnished(self):
        assert DescriptionParser.extract_furniture_level("Fully furnished room") == "fully_furnished"

    def test_completely_furnished(self):
        assert DescriptionParser.extract_furniture_level("Completely furnished with everything") == "fully_furnished"

    def test_turnkey(self):
        assert DescriptionParser.extract_furniture_level("Turn-key unit, just bring your clothes") == "fully_furnished"

    def test_partially_furnished(self):
        assert DescriptionParser.extract_furniture_level("Partially furnished, bed included") == "partially_furnished"

    def test_furnished_with_items(self):
        assert DescriptionParser.extract_furniture_level("Furnished with bed and desk") == "partially_furnished"

    def test_unfurnished(self):
        assert DescriptionParser.extract_furniture_level("Unfurnished room, bring your own furniture") == "unfurnished"

    def test_bare_furnished(self):
        # "furnished" alone defaults to fully
        assert DescriptionParser.extract_furniture_level("Room is furnished") == "fully_furnished"

    def test_no_signal(self):
        assert DescriptionParser.extract_furniture_level("Room near SkyTrain, $900/mo") is None


class TestNeighbourhoodNormalization:
    def test_downtown(self):
        assert DescriptionParser.normalize_neighbourhood("Room in downtown Vancouver") == "Downtown"

    def test_kitsilano(self):
        assert DescriptionParser.normalize_neighbourhood("Kits area, near the beach") == "Kitsilano"

    def test_kits_abbreviation(self):
        assert DescriptionParser.normalize_neighbourhood("Beautiful space in Kits") == "Kitsilano"

    def test_mount_pleasant(self):
        assert DescriptionParser.normalize_neighbourhood("Mount Pleasant, near Main St") == "Mount Pleasant"

    def test_east_vancouver(self):
        assert DescriptionParser.normalize_neighbourhood("East Vancouver, great neighbourhood") == "East Vancouver"

    def test_hastings_sunrise(self):
        assert DescriptionParser.normalize_neighbourhood("Hastings-Sunrise, Vancouver") == "Hastings-Sunrise"

    def test_commercial_drive(self):
        assert DescriptionParser.normalize_neighbourhood("Near Commercial Drive, vibrant area") == "Grandview-Woodland"

    def test_burnaby(self):
        assert DescriptionParser.normalize_neighbourhood("Located in Burnaby") == "Burnaby"

    def test_river_district(self):
        assert DescriptionParser.normalize_neighbourhood("South Marine, Vancouver") == "River District"

    def test_unknown_location(self):
        assert DescriptionParser.normalize_neighbourhood("Nice place for rent") is None


class TestParseAll:
    def test_real_listing_snippet(self):
        """Test with a realistic Kijiji description."""
        result = DescriptionParser.parse_all(
            description=(
                "ROOMS AVAILABLE - Main floor private bedroom (April 1st) "
                "Welcome to a well maintained townhouse featuring lofty high ceilings. "
                "Shared bathroom with one other tenant. Fully furnished room includes "
                "bed, desk, and closet. Laundry in building. Female only please. "
                "Month to month rental. 5 min walk to Joyce-Collingwood SkyTrain."
            ),
            title="Sunny townhouse share by River District, private bedroom",
            location="South Marine, Vancouver",
        )
        assert result["gender_preference"] == "female_only"
        assert result["lease_type"] == "month_to_month"
        assert result["bathroom_type"] == "shared"
        assert result["furniture_level"] == "fully_furnished"
        assert result["transit_proximity"] == "near_skytrain"
        assert result["transit_description"] is not None
        assert result["neighbourhood"] == "River District"

    def test_sparse_listing(self):
        """Test with a minimal description."""
        result = DescriptionParser.parse_all(
            description="Room for rent. $950/month. Available now.",
            title="One Private Bedroom For Rent",
            location="Hastings-Sunrise, Vancouver",
        )
        assert result["neighbourhood"] == "Hastings-Sunrise"
        # Most fields should be None for sparse listings
        assert result["gender_preference"] is None
        assert result["lease_type"] is None
