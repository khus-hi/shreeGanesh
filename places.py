"""
US states and tech-hub metros.
- Used by discovery: Google searches rotate through every tech-hub city and every state.
- Used to tag each job with its tech-hub metro (Excel "Metro" column).
Add or remove cities freely.
"""

import re

STATE_NAMES = [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware",
    "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky",
    "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", "Mississippi",
    "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico",
    "New York", "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", "Pennsylvania",
    "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont",
    "Virginia", "Washington", "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
]

# metro name -> cities/suburbs that belong to it (first city = the one Google searches use)
TECH_HUBS = {
    "SF Bay Area": ["San Francisco", "San Jose", "Palo Alto", "Mountain View", "Sunnyvale", "Santa Clara",
                    "Menlo Park", "Redwood City", "Cupertino", "Oakland", "Fremont", "San Mateo", "Milpitas",
                    "South San Francisco", "Foster City", "Emeryville", "Berkeley"],
    "Seattle": ["Seattle", "Bellevue", "Redmond", "Kirkland", "Bothell", "Tacoma"],
    "New York City": ["New York", "NYC", "Manhattan", "Brooklyn", "Jersey City", "Hoboken", "Newark", "Stamford"],
    "Boston": ["Boston", "Cambridge", "Waltham", "Somerville", "Burlington", "Lexington", "Needham",
               "Quincy", "Woburn", "Bedford", "Marlborough"],
    "Austin": ["Austin", "Round Rock"],
    "Los Angeles": ["Los Angeles", "Santa Monica", "Culver City", "Playa Vista", "Pasadena", "Burbank",
                    "Irvine", "El Segundo", "Long Beach", "Glendale"],
    "San Diego": ["San Diego", "La Jolla", "Carlsbad"],
    "Washington DC": ["Washington", "Arlington", "Reston", "McLean", "Herndon", "Tysons", "Alexandria",
                      "Bethesda", "Rockville", "Chantilly", "Fairfax", "Vienna"],
    "Chicago": ["Chicago", "Evanston", "Schaumburg", "Naperville", "Deerfield"],
    "Denver/Boulder": ["Denver", "Boulder", "Broomfield", "Englewood", "Louisville"],
    "Atlanta": ["Atlanta", "Alpharetta", "Marietta"],
    "Dallas": ["Dallas", "Plano", "Irving", "Frisco", "Richardson", "Fort Worth", "Addison"],
    "Houston": ["Houston", "The Woodlands", "Sugar Land"],
    "Raleigh-Durham": ["Raleigh", "Durham", "Cary", "Research Triangle", "Chapel Hill", "Morrisville"],
    "Philadelphia": ["Philadelphia", "King of Prussia", "Conshohocken", "Wilmington"],
    "Pittsburgh": ["Pittsburgh"],
    "Minneapolis": ["Minneapolis", "St. Paul", "Saint Paul", "Bloomington", "Eden Prairie"],
    "Salt Lake City": ["Salt Lake City", "Lehi", "Provo", "Draper", "South Jordan"],
    "Phoenix": ["Phoenix", "Tempe", "Scottsdale", "Chandler"],
    "Portland": ["Portland", "Beaverton", "Hillsboro"],
    "Miami": ["Miami", "Fort Lauderdale", "Boca Raton"],
    "Nashville": ["Nashville", "Franklin"],
    "Charlotte": ["Charlotte"],
    "Detroit/Ann Arbor": ["Detroit", "Ann Arbor", "Dearborn", "Troy"],
    "Columbus": ["Columbus", "Dublin"],
    "Baltimore": ["Baltimore", "Columbia"],
    "St. Louis": ["St. Louis", "Saint Louis"],
    "Kansas City": ["Kansas City", "Overland Park"],
    "Madison": ["Madison"],
    "Richmond": ["Richmond"],
    "Tampa": ["Tampa", "St. Petersburg"],
    "Las Vegas": ["Las Vegas"],
}

# cities used in Google discovery searches (main city of each hub + a few big extra ones)
_SEARCH_NAME = {"Washington": "Washington, DC", "Portland": "Portland, OR", "Columbus": "Columbus, OH",
                "Richmond": "Richmond, VA", "Madison": "Madison, WI", "Charlotte": "Charlotte, NC",
                "Kansas City": "Kansas City", "Baltimore": "Baltimore", "Austin": "Austin, TX"}
HUB_SEARCH_CITIES = [_SEARCH_NAME.get(cities[0], cities[0]) for cities in TECH_HUBS.values()] + [
    "Cambridge, MA", "Palo Alto", "Bellevue", "Jersey City", "Plano", "Irvine", "Arlington, VA",
]

# city names that also exist elsewhere -> only count them with the right state
AMBIGUOUS = {"Washington": "DC", "Portland": "OR", "Columbia": "MD", "Dublin": "OH", "Franklin": "TN",
             "Cambridge": "MA", "Arlington": "VA", "Burlington": "MA", "Richmond": "VA", "Columbus": "OH",
             "Vienna": "VA", "Glendale": "CA", "Bloomington": "MN", "Lexington": "MA", "Wilmington": "DE",
             "Troy": "MI", "Louisville": "CO", "Bedford": "MA", "Kansas City": "", "Long Beach": "CA",
             "Quincy": "MA", "Fairfax": "VA", "Newark": "NJ", "Stamford": "CT", "Madison": "WI"}

_HUB_RES = [
    (metro, city, re.compile(r"\b" + re.escape(city) + r"\b", re.I))
    for metro, cities in TECH_HUBS.items() for city in cities
]


def metro_of(location, states=""):
    """'Cambridge, MA' -> 'Boston'; returns '' if not in a tech hub."""
    loc = location or ""
    found = []
    for metro, city, rx in _HUB_RES:
        if rx.search(loc):
            need = AMBIGUOUS.get(city)
            if need and need not in (states or "") and need not in loc:
                continue
            if metro not in found:
                found.append(metro)
    return ", ".join(found)
