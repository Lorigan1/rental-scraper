"""Tests for the description parser V2 — comprehensive extraction."""

import pytest
from rental_scraper.description_parser import DescriptionParser


# ── Gender preference ────────────────────────────────────────

class TestGenderPreference:
    def test_female_only(self):
        assert DescriptionParser.extract_gender_preference("Female only please") == "female_only"

    def test_male_only(self):
        assert DescriptionParser.extract_gender_preference("Male preferred") == "male_only"

    def test_couples_welcome(self):
        assert DescriptionParser.extract_gender_preference("Couples welcome!") == "couples_welcome"

    def test_no_couples(self):
        assert DescriptionParser.extract_gender_preference("No couples sorry") == "no_couples"

    def test_single_occupancy(self):
        assert DescriptionParser.extract_gender_preference("Single occupancy only (no couples, sorry)") == "no_couples"

    def test_female_before_couples(self):
        assert DescriptionParser.extract_gender_preference("Female only, no couples") == "no_couples"

    def test_for_a_woman(self):
        assert DescriptionParser.extract_gender_preference("Room for a woman") == "female_only"

    def test_no_match(self):
        assert DescriptionParser.extract_gender_preference("Spacious room available") is None


# ── Couples allowed ──────────────────────────────────────────

class TestCouplesAllowed:
    def test_no_couples(self):
        assert DescriptionParser.extract_couples_allowed("No couples") is False

    def test_couples_ok(self):
        assert DescriptionParser.extract_couples_allowed("Couples ok") is True

    def test_single_occupancy(self):
        assert DescriptionParser.extract_couples_allowed("Single occupancy only") is False

    def test_no_match(self):
        assert DescriptionParser.extract_couples_allowed("Nice room") is None


# ── Smoking ──────────────────────────────────────────────────

class TestSmoking:
    def test_no_smoking(self):
        assert DescriptionParser.extract_smoking("No smoking") is False

    def test_non_smoker(self):
        assert DescriptionParser.extract_smoking("Non-smoker preferred") is False

    def test_smoke_free(self):
        assert DescriptionParser.extract_smoking("Smoke-free building") is False

    def test_doesnt_smoke(self):
        assert DescriptionParser.extract_smoking("doesn't smoke") is False

    def test_smoking_ok(self):
        assert DescriptionParser.extract_smoking("Smoking ok outside") is True

    def test_no_match(self):
        assert DescriptionParser.extract_smoking("Great view") is None


# ── Age range ────────────────────────────────────────────────

class TestAgeRange:
    def test_in_their_20_30s(self):
        result = DescriptionParser.extract_age_range("someone who's in their 20-30's")
        assert result["age_range_min"] == 20
        assert result["age_range_max"] == 30

    def test_20s_and_30s(self):
        result = DescriptionParser.extract_age_range("looking for someone in their 20s and 30s")
        assert result["age_range_min"] == 20
        assert result["age_range_max"] == 30

    def test_ages_25_to_40(self):
        result = DescriptionParser.extract_age_range("ages 25 to 40")
        assert result["age_range_min"] == 25
        assert result["age_range_max"] == 40

    def test_between_25_35(self):
        result = DescriptionParser.extract_age_range("between 25-35 years old")
        assert result["age_range_min"] == 25
        assert result["age_range_max"] == 35

    def test_no_match(self):
        result = DescriptionParser.extract_age_range("Room available near UBC")
        assert result["age_range_min"] is None
        assert result["age_range_max"] is None


# ── Vibe ─────────────────────────────────────────────────────

class TestVibe:
    def test_quiet(self):
        assert DescriptionParser.extract_vibe("Quiet household") == "quiet"

    def test_laid_back(self):
        assert DescriptionParser.extract_vibe("laid-back lifestyle") == "quiet"

    def test_professional(self):
        assert DescriptionParser.extract_vibe("working professional preferred") == "professional"

    def test_student(self):
        assert DescriptionParser.extract_vibe("near university, great for students") == "student"

    def test_social(self):
        assert DescriptionParser.extract_vibe("Social, outgoing household") == "social"

    def test_420_friendly(self):
        assert DescriptionParser.extract_vibe("420-friendly house") == "social"

    def test_no_match(self):
        assert DescriptionParser.extract_vibe("2 bedroom apartment") is None


# ── Lease type ───────────────────────────────────────────────

class TestLeaseType:
    def test_month_to_month(self):
        assert DescriptionParser.extract_lease_type("month-to-month lease") == "month_to_month"

    def test_m2m(self):
        assert DescriptionParser.extract_lease_type("M2M available") == "month_to_month"

    def test_no_lease(self):
        assert DescriptionParser.extract_lease_type("no lease required") == "month_to_month"

    def test_fixed_term(self):
        assert DescriptionParser.extract_lease_type("Minimum 6 months commitment") == "fixed_term"

    def test_lease_required(self):
        assert DescriptionParser.extract_lease_type("Lease required") == "fixed_term"

    def test_annual_lease(self):
        assert DescriptionParser.extract_lease_type("One-year lease preferred") == "fixed_term"

    def test_sublet(self):
        assert DescriptionParser.extract_lease_type("Minimum 3-month sublet") == "fixed_term"

    def test_no_match(self):
        assert DescriptionParser.extract_lease_type("Nice place") is None


# ── Min lease months ─────────────────────────────────────────

class TestMinLeaseMonths:
    def test_minimum_6_months(self):
        assert DescriptionParser.extract_min_lease_months("Minimum 6 months") == 6

    def test_12_month_lease(self):
        assert DescriptionParser.extract_min_lease_months("12 month lease") == 12

    def test_1_year_minimum(self):
        assert DescriptionParser.extract_min_lease_months("1 year minimum") == 12

    def test_3_month_sublet(self):
        assert DescriptionParser.extract_min_lease_months("Minimum 3-month sublet, with the possibility of extending") == 3

    def test_out_of_range(self):
        assert DescriptionParser.extract_min_lease_months("Minimum 100 months") is None


# ── Available from ───────────────────────────────────────────

class TestAvailableFrom:
    def test_april_1_2026(self):
        assert DescriptionParser.extract_available_from("Available April 1, 2026") == "2026-04-01"

    def test_immediately(self):
        assert DescriptionParser.extract_available_from("Available immediately") == "immediate"

    def test_now(self):
        assert DescriptionParser.extract_available_from("Move-in now") == "immediate"

    def test_iso_date(self):
        assert DescriptionParser.extract_available_from("Available 2026-05-15") == "2026-05-15"

    def test_no_match(self):
        assert DescriptionParser.extract_available_from("Nice room for rent") is None


# ── Price range ──────────────────────────────────────────────

class TestPriceRange:
    def test_range_with_dash(self):
        result = DescriptionParser.extract_price_range("Rent: $1,300 – $2,300/month")
        assert result["price_min"] == 1300
        assert result["price_max"] == 2300

    def test_range_without_comma(self):
        result = DescriptionParser.extract_price_range("$800-$1200/mo")
        assert result["price_min"] == 800
        assert result["price_max"] == 1200

    def test_no_range(self):
        result = DescriptionParser.extract_price_range("$1200/month")
        assert result["price_min"] is None
        assert result["price_max"] is None


# ── Building type ────────────────────────────────────────────

class TestBuildingType:
    def test_high_rise(self):
        assert DescriptionParser.extract_building_type("modern high-rise building") == "high_rise"

    def test_tower(self):
        assert DescriptionParser.extract_building_type("condo tower downtown") == "high_rise"

    def test_low_rise(self):
        assert DescriptionParser.extract_building_type("low-rise apartment") == "low_rise"

    def test_townhouse(self):
        assert DescriptionParser.extract_building_type("townhouse on Main St") == "townhouse"

    def test_basement(self):
        assert DescriptionParser.extract_building_type("basement suite available") == "basement"

    def test_laneway(self):
        assert DescriptionParser.extract_building_type("laneway house") == "laneway"

    def test_house(self):
        assert DescriptionParser.extract_building_type("single family house") == "house"

    def test_no_match(self):
        assert DescriptionParser.extract_building_type("room for rent") is None


# ── Domicile type ────────────────────────────────────────────

class TestDomicileType:
    def test_condo(self):
        assert DescriptionParser.extract_domicile_type("condo near skytrain") == "condo"

    def test_apartment(self):
        assert DescriptionParser.extract_domicile_type("apartment in Kitsilano") == "apartment"

    def test_townhouse(self):
        assert DescriptionParser.extract_domicile_type("townhome in Burnaby") == "townhouse"

    def test_studio(self):
        assert DescriptionParser.extract_domicile_type("bachelor studio") == "studio"

    def test_suite(self):
        assert DescriptionParser.extract_domicile_type("basement suite") == "suite"

    def test_no_match(self):
        assert DescriptionParser.extract_domicile_type("room for rent") is None


# ── Room type ────────────────────────────────────────────────

class TestRoomType:
    def test_master(self):
        assert DescriptionParser.extract_room_type("master bedroom available") == "master"

    def test_primary(self):
        assert DescriptionParser.extract_room_type("primary bedroom with ensuite") == "master"

    def test_den(self):
        assert DescriptionParser.extract_room_type("converted den for rent") == "den"

    def test_shared_room(self):
        assert DescriptionParser.extract_room_type("shared room, 2 bunk beds") == "shared_room"

    def test_private_room(self):
        assert DescriptionParser.extract_room_type("private room in shared apartment") == "private_room"

    def test_no_match(self):
        assert DescriptionParser.extract_room_type("apartment for rent") is None


# ── Shared living ────────────────────────────────────────────

class TestSharedLiving:
    def test_shared_apartment(self):
        assert DescriptionParser.extract_shared_living("room in a shared apartment") is True

    def test_roommate_wanted(self):
        assert DescriptionParser.extract_shared_living("Roommate wanted") is True

    def test_looking_for_roommate(self):
        assert DescriptionParser.extract_shared_living("Looking for a roommate") is True

    def test_entire_unit(self):
        assert DescriptionParser.extract_shared_living("Entire unit available") is False

    def test_no_match(self):
        assert DescriptionParser.extract_shared_living("Nice place") is None


# ── Furnished bedroom ────────────────────────────────────────

class TestFurnishedBedroom:
    def test_furnished_bedroom(self):
        assert DescriptionParser.extract_furnished_bedroom("furnished bedroom available") is True

    def test_private_furnished(self):
        assert DescriptionParser.extract_furnished_bedroom("Private furnished bedroom") is True

    def test_room_comes_furnished(self):
        assert DescriptionParser.extract_furnished_bedroom("room comes fully furnished") is True

    def test_unfurnished_bedroom(self):
        assert DescriptionParser.extract_furnished_bedroom("unfurnished bedroom") is False

    def test_bring_own(self):
        assert DescriptionParser.extract_furnished_bedroom("bring your own bed") is False

    def test_no_match(self):
        assert DescriptionParser.extract_furnished_bedroom("nice location") is None


# ── Furnished common ─────────────────────────────────────────

class TestFurnishedCommon:
    def test_shared_spaces_furnished(self):
        assert DescriptionParser.extract_furnished_common("Shared spaces are fully furnished") is True

    def test_furnished_common_area(self):
        assert DescriptionParser.extract_furnished_common("Furnished common area") is True

    def test_common_areas_furnished(self):
        assert DescriptionParser.extract_furnished_common("common areas fully furnished") is True

    def test_no_match(self):
        assert DescriptionParser.extract_furnished_common("nice kitchen") is None


# ── Furniture level ──────────────────────────────────────────

class TestFurnitureLevel:
    def test_unfurnished(self):
        assert DescriptionParser.extract_furniture_level("unfurnished unit") == "unfurnished"

    def test_fully_furnished(self):
        assert DescriptionParser.extract_furniture_level("Fully furnished suite") == "fully_furnished"

    def test_partially(self):
        assert DescriptionParser.extract_furniture_level("Partially furnished") == "partially_furnished"

    def test_turn_key(self):
        assert DescriptionParser.extract_furniture_level("Turn-key ready") == "fully_furnished"

    def test_bare_furnished(self):
        assert DescriptionParser.extract_furniture_level("The room is furnished") == "fully_furnished"

    def test_no_furniture(self):
        assert DescriptionParser.extract_furniture_level("No furniture provided") == "unfurnished"


# ── Bathroom type ────────────────────────────────────────────

class TestBathroomType:
    def test_private_bathroom(self):
        assert DescriptionParser.extract_bathroom_type("private bathroom") == "private"

    def test_ensuite(self):
        assert DescriptionParser.extract_bathroom_type("with ensuite bathroom") == "private"

    def test_en_suite(self):
        assert DescriptionParser.extract_bathroom_type("full en-suite bath") == "private"

    def test_own_bathroom(self):
        assert DescriptionParser.extract_bathroom_type("your own bathroom") == "private"

    def test_shared_bathroom(self):
        assert DescriptionParser.extract_bathroom_type("shared bathroom") == "shared"

    def test_no_match(self):
        assert DescriptionParser.extract_bathroom_type("2 bathrooms total") is None


# ── Laundry type ─────────────────────────────────────────────

class TestLaundryType:
    def test_in_unit(self):
        assert DescriptionParser.extract_laundry_type("Laundry in unit") == "in_unit"

    def test_in_suite_washer(self):
        assert DescriptionParser.extract_laundry_type("In-suite washer/dryer") == "in_unit"

    def test_w_d_in_unit(self):
        assert DescriptionParser.extract_laundry_type("W/D in unit") == "in_unit"

    def test_shared_laundry(self):
        assert DescriptionParser.extract_laundry_type("Shared laundry in building") == "in_building"

    def test_coin_laundry(self):
        assert DescriptionParser.extract_laundry_type("Coin laundry downstairs") == "in_building"

    def test_no_match(self):
        assert DescriptionParser.extract_laundry_type("Great location") is None


# ── Transit proximity ────────────────────────────────────────

class TestTransitProximity:
    def test_near_skytrain(self):
        assert DescriptionParser.extract_transit_proximity("Near the SkyTrain") == "near_skytrain"

    def test_walk_to_skytrain(self):
        assert DescriptionParser.extract_transit_proximity("5 min walk to skytrain") == "near_skytrain"

    def test_station_name(self):
        assert DescriptionParser.extract_transit_proximity("close to Metrotown station skytrain") == "near_skytrain"

    def test_near_bus(self):
        assert DescriptionParser.extract_transit_proximity("Near the bus stop") == "near_bus"

    def test_good_transit(self):
        assert DescriptionParser.extract_transit_proximity("Excellent transit access") == "good_transit"

    def test_transit_friendly(self):
        assert DescriptionParser.extract_transit_proximity("Transit-friendly location") == "good_transit"

    def test_no_match(self):
        assert DescriptionParser.extract_transit_proximity("Quiet residential area") is None


# ── Amenities ────────────────────────────────────────────────

class TestAmenities:
    def test_dishwasher(self):
        assert DescriptionParser.extract_dishwasher("kitchen with dishwasher") is True

    def test_no_dishwasher(self):
        assert DescriptionParser.extract_dishwasher("nice kitchen") is None

    def test_balcony(self):
        assert DescriptionParser.extract_balcony("2 balconies") is True

    def test_patio(self):
        assert DescriptionParser.extract_balcony("private patio") is True

    def test_deck(self):
        assert DescriptionParser.extract_balcony("large deck") is True

    def test_fireplace(self):
        assert DescriptionParser.extract_fireplace("gas fireplace in living room") is True

    def test_ac(self):
        assert DescriptionParser.extract_ac("Air conditioning included") is True

    def test_ac_abbreviation(self):
        assert DescriptionParser.extract_ac("Unit has A/C") is True

    def test_ev_charging(self):
        assert DescriptionParser.extract_ev_charging("EV charging available") is True

    def test_gym(self):
        assert DescriptionParser.extract_gym("Building has gym") is True

    def test_fitness_centre(self):
        assert DescriptionParser.extract_gym("Fitness centre on-site") is True

    def test_storage(self):
        assert DescriptionParser.extract_storage("Storage locker included") is True


# ── Close to amenities ───────────────────────────────────────

class TestCloseToAmenities:
    def test_walkable(self):
        assert DescriptionParser.extract_amenities_proximity("Walkable to lots of grocery stores, cafes") is True

    def test_close_to_shops(self):
        assert DescriptionParser.extract_amenities_proximity("Close to shops and restaurants") is True

    def test_near_amenities(self):
        assert DescriptionParser.extract_amenities_proximity("Near all amenities") is True

    def test_no_match(self):
        assert DescriptionParser.extract_amenities_proximity("Quiet street") is None


# ── Views ────────────────────────────────────────────────────

class TestViews:
    def test_city_view(self):
        assert DescriptionParser.extract_views("rooms with city views") is True

    def test_mountain_view(self):
        assert DescriptionParser.extract_views("beautiful mountain view") is True

    def test_with_views(self):
        assert DescriptionParser.extract_views("select rooms with stunning views") is True

    def test_no_match(self):
        assert DescriptionParser.extract_views("ground floor unit") is None


# ── Utilities ────────────────────────────────────────────────

class TestUtilities:
    def test_utilities_included(self):
        assert DescriptionParser.extract_utilities("Utilities included") is True

    def test_all_inclusive(self):
        assert DescriptionParser.extract_utilities("All-inclusive rent") is True

    def test_hydro_included(self):
        assert DescriptionParser.extract_utilities("Hydro included") is True

    def test_no_utilities(self):
        assert DescriptionParser.extract_utilities("Utilities not included") is False

    def test_utilities_extra(self):
        assert DescriptionParser.extract_utilities("Utilities extra") is False

    def test_no_match(self):
        assert DescriptionParser.extract_utilities("Nice place") is None


# ── Parking ──────────────────────────────────────────────────

class TestParking:
    def test_parking_included(self):
        assert DescriptionParser.extract_parking("Parking included") is True

    def test_underground_parking(self):
        assert DescriptionParser.extract_parking("Underground parking spaces included") is True

    def test_1_parking_spot(self):
        assert DescriptionParser.extract_parking("1 parking spot available") is True

    def test_no_parking(self):
        assert DescriptionParser.extract_parking("No parking available") is False

    def test_street_only(self):
        assert DescriptionParser.extract_parking("Street parking only") is False


# ── Pets ─────────────────────────────────────────────────────

class TestPets:
    def test_pet_friendly(self):
        assert DescriptionParser.extract_pets("Pet-friendly building") is True

    def test_cats_ok(self):
        assert DescriptionParser.extract_pets("Cats ok") is True

    def test_no_pets(self):
        assert DescriptionParser.extract_pets("No pets allowed") is False

    def test_sorry_no_pets(self):
        assert DescriptionParser.extract_pets("Sorry no pets") is False


# ── Bedrooms ─────────────────────────────────────────────────

class TestBedrooms:
    def test_2br(self):
        assert DescriptionParser.extract_bedrooms("$2,050 / 2br") == 2

    def test_2_bedroom(self):
        assert DescriptionParser.extract_bedrooms("2-bedroom apartment") == 2

    def test_3_bed(self):
        assert DescriptionParser.extract_bedrooms("3 bed house") == 3

    def test_no_match(self):
        assert DescriptionParser.extract_bedrooms("nice room") is None


# ── Bathrooms ────────────────────────────────────────────────

class TestBathrooms:
    def test_2_bathroom(self):
        assert DescriptionParser.extract_bathrooms("2-bathroom apartment") == 2

    def test_1_bath(self):
        assert DescriptionParser.extract_bathrooms("1 bath") == 1

    def test_no_match(self):
        assert DescriptionParser.extract_bathrooms("nice room") is None


# ── Neighbourhood normalization ──────────────────────────────

class TestNeighbourhoodNormalization:
    def test_kitsilano(self):
        assert DescriptionParser.normalize_neighbourhood("Room in Kitsilano") == "Kitsilano"

    def test_kits(self):
        assert DescriptionParser.normalize_neighbourhood("Kits apartment") == "Kitsilano"

    def test_collingwood_vancouver(self):
        assert DescriptionParser.normalize_neighbourhood("Collingwood, Vancouver") == "Renfrew-Collingwood"

    def test_renfrew_collingwood(self):
        assert DescriptionParser.normalize_neighbourhood("Renfrew-Collingwood") == "Renfrew-Collingwood"

    def test_renfrew_alone(self):
        assert DescriptionParser.normalize_neighbourhood("Renfrew area") == "Renfrew-Collingwood"

    def test_commercial_drive(self):
        assert DescriptionParser.normalize_neighbourhood("Near Commercial Drive") == "Grandview-Woodland"

    def test_ubc(self):
        assert DescriptionParser.normalize_neighbourhood("Near UBC campus") == "UBC"

    def test_metrotown(self):
        assert DescriptionParser.normalize_neighbourhood("Near Metrotown") == "Burnaby — Metrotown"

    def test_burnaby_general(self):
        assert DescriptionParser.normalize_neighbourhood("Burnaby location") == "Burnaby"

    def test_downtown(self):
        assert DescriptionParser.normalize_neighbourhood("Downtown Vancouver") == "Downtown"

    def test_mount_pleasant(self):
        assert DescriptionParser.normalize_neighbourhood("Mt. Pleasant neighbourhood") == "Mount Pleasant"

    def test_new_west(self):
        assert DescriptionParser.normalize_neighbourhood("New West near Sapperton") == "New Westminster"

    def test_north_van(self):
        assert DescriptionParser.normalize_neighbourhood("North Van near Lonsdale") == "North Vancouver"

    def test_richmond(self):
        assert DescriptionParser.normalize_neighbourhood("Richmond area") == "Richmond"

    def test_west_end(self):
        assert DescriptionParser.normalize_neighbourhood("English Bay, West End") == "West End"

    def test_coal_harbour(self):
        assert DescriptionParser.normalize_neighbourhood("Coal Harbour condo") == "Coal Harbour"

    def test_joyce_collingwood(self):
        assert DescriptionParser.normalize_neighbourhood("Joyce-Collingwood area") == "Renfrew-Collingwood"

    def test_no_match(self):
        assert DescriptionParser.normalize_neighbourhood("Great location!") is None


# ── Integration: Real Kijiji listing ─────────────────────────

class TestIntegrationKijiji:
    """Test with the real Kijiji listing from user example."""

    TEXT = (
        "Downtown Vancouver Private Rooms High-Rise Living. "
        "Private, fully furnished bedrooms available in a modern high-rise "
        "shared apartment in downtown Vancouver. "
        "Rent: $1,300 – $2,300/month. Multiple rooms available. "
        "What's Included: Private furnished bedroom. All utilities included. "
        "High-speed internet. In-unit laundry. Maid service for common areas. "
        "Select rooms with city views. "
        "One monthly payment. No hidden costs. Move-in ready. "
        "Discounted rates available with a 1-year lease. "
        "Non-smoking building."
    )

    def test_full_parse(self):
        result = DescriptionParser.parse_all(self.TEXT, "Downtown Rooms", "Vancouver")

        assert result["neighbourhood"] == "Downtown"
        assert result["building_type"] == "high_rise"
        assert result["domicile_type"] == "apartment"
        assert result["shared_living"] is True
        assert result["furnished_bedroom"] is True
        assert result["utilities_included"] is True
        assert result["laundry_type"] == "in_unit"
        assert result["has_views"] is True
        assert result["smoking_allowed"] is False
        assert result["price_min"] == 1300
        assert result["price_max"] == 2300
        assert result["furniture_level"] == "fully_furnished"


# ── Integration: Real Craigslist listing ─────────────────────

class TestIntegrationCraigslist:
    """Test with the real Craigslist listing from user example."""

    TITLE = "$2,050 / 2br - 1000ft2 - Master Bedroom in Sunny Large Kitsilano Apartment (Kitsilano, Vancouver)"
    TEXT = (
        "Hi there! I'm looking for a roommate to rent the master bedroom "
        "in a 2-bedroom, 2-bathroom apartment in lovely Kitsilano. "
        "The master is very spacious with two closets and a full private bathroom. "
        "I'm looking for someone who's in their 20-30's and is a working professional, "
        "clean, respectful of each other's space, and doesn't smoke. "
        "The apartment is in an amazing location at Broadway & Yew St. "
        "and a 15-minute walk to Kitsilano Beach. "
        "Walkable to lots of grocery stores, cafes, parks, etc. "
        "2 bedroom, 2 bath. Approx. 1,000 sqft. "
        "Shared spaces are fully furnished. "
        "Large modern kitchen with dishwasher, microwave, etc. "
        "In-suite washer/dryer. 2 balconies (East and North-facing). "
        "Fireplace. Underground parking spaces included. "
        "Single occupancy only (no couples, sorry). "
        "Utilities included. Available April 1, 2026. "
        "Minimum 3-month sublet, with the possibility of extending."
    )

    def test_full_parse(self):
        result = DescriptionParser.parse_all(self.TEXT, self.TITLE, "Kitsilano, Vancouver")

        assert result["neighbourhood"] == "Kitsilano"
        assert result["room_type"] == "master"
        assert result["bathroom_type"] == "private"
        assert result["smoking_allowed"] is False
        assert result["age_range_min"] == 20
        assert result["age_range_max"] == 30
        assert result["vibe"] == "professional"
        assert result["close_to_amenities"] is True
        assert result["furnished_common"] is True
        assert result["dishwasher"] is True
        assert result["laundry_type"] == "in_unit"
        assert result["balcony"] is True
        assert result["fireplace"] is True
        assert result["parking_included"] is True
        assert result["gender_preference"] == "no_couples"
        assert result["couples_allowed"] is False
        assert result["utilities_included"] is True
        assert result["available_from"] == "2026-04-01"
        assert result["min_lease_months"] == 3
        assert result["lease_type"] == "fixed_term"
        assert result["shared_living"] is True
        assert result["num_bedrooms"] == 2
        assert result["num_bathrooms"] == 2
