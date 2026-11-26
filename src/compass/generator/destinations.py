"""The 38 destinations Compass Assistance covers, in three regions.

Reference data: it goes into the warehouse as-is.
"""

# (city, state_or_country, airport_code, region, hotel_rate per night)
DESTINATIONS: list[tuple[str, str, str, str, float]] = [
    # US Atlantic
    ("Miami Beach", "FL", "MIA", "us_atlantic", 280),
    ("Fort Lauderdale", "FL", "FLL", "us_atlantic", 250),
    ("Key West", "FL", "EYW", "us_atlantic", 320),
    ("Naples", "FL", "RSW", "us_atlantic", 270),
    ("Tampa", "FL", "TPA", "us_atlantic", 200),
    ("Jacksonville", "FL", "JAX", "us_atlantic", 170),
    ("Savannah", "GA", "SAV", "us_atlantic", 190),
    ("Charleston", "SC", "CHS", "us_atlantic", 220),
    ("Myrtle Beach", "SC", "MYR", "us_atlantic", 180),
    ("Outer Banks", "NC", "OGX", "us_atlantic", 200),
    ("Virginia Beach", "VA", "ORF", "us_atlantic", 180),
    ("Ocean City", "MD", "SBY", "us_atlantic", 175),
    ("Atlantic City", "NJ", "ACY", "us_atlantic", 190),
    ("The Hamptons", "NY", "ISP", "us_atlantic", 350),
    # US Gulf Coast
    ("Galveston", "TX", "IAH", "gulf_coast", 170),
    ("South Padre Island", "TX", "BRO", "gulf_coast", 185),
    ("Gulf Shores", "AL", "PNS", "gulf_coast", 175),
    ("Pensacola", "FL", "PNS", "gulf_coast", 165),
    ("Panama City Beach", "FL", "ECP", "gulf_coast", 180),
    ("New Orleans", "LA", "MSY", "gulf_coast", 210),
    # Caribbean
    ("San Juan", "PR", "SJU", "caribbean", 250),
    ("Ponce", "PR", "PSE", "caribbean", 200),
    ("St. Thomas", "USVI", "STT", "caribbean", 300),
    ("St. Croix", "USVI", "STX", "caribbean", 275),
    ("Nassau", "Bahamas", "NAS", "caribbean", 320),
    ("Freeport", "Bahamas", "FPO", "caribbean", 260),
    ("Punta Cana", "DR", "PUJ", "caribbean", 350),
    ("Santo Domingo", "DR", "SDQ", "caribbean", 220),
    ("Montego Bay", "Jamaica", "MBJ", "caribbean", 310),
    ("Cancún", "Mexico", "CUN", "caribbean", 280),
    ("Playa del Carmen", "Mexico", "CUN", "caribbean", 250),
    ("Cozumel", "Mexico", "CZM", "caribbean", 240),
    ("Grand Cayman", "Cayman Islands", "GCM", "caribbean", 380),
    ("Turks & Caicos", "Turks and Caicos", "PLS", "caribbean", 400),
    ("St. Maarten", "St. Maarten", "SXM", "caribbean", 330),
    ("Aruba", "Aruba", "AUA", "caribbean", 350),
    ("Barbados", "Barbados", "BGI", "caribbean", 300),
    ("Bermuda", "Bermuda", "BDA", "caribbean", 420),
]

REGIONS = ("us_atlantic", "gulf_coast", "caribbean")
