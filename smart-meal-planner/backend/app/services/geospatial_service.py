
import math
from typing import Optional, Tuple

class GeospatialService:
    # A small FSA mapping for common Montreal-area postal codes.
    # In a production app, this could be a more comprehensive database or an external API.
    FSA_MAPPING = {
        "H4T": (45.4954, -73.6798),
        "H4B": (45.4600, -73.6300),
        "H2X": (45.5100, -73.5700),
        "H3G": (45.4975, -73.5786),
        "H1A": (45.6800, -73.5000),
        "H4E": (45.4542, -73.5855),
        "H3Z": (45.4852, -73.5960),
        "H2L": (45.5190, -73.5564),
    }

    @classmethod
    def get_coordinates(cls, postal_code: str) -> Optional[Tuple[float, float]]:
        """
        Returns (latitude, longitude) for a given Canadian postal code.
        Uses the FSA (first 3 characters) for approximation.
        """
        if not postal_code:
            return None

        fsa = postal_code[:3].upper()
        return cls.FSA_MAPPING.get(fsa)

    @staticmethod
    def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculates the Haversine distance between two points in kilometers.
        """
        R = 6371.0  # Earth radius in km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    @classmethod
    def get_distance_between_postal_codes(cls, pc1: str, pc2: str) -> Optional[float]:
        """
        Calculates distance between two postal codes in kilometers.
        Returns None if coordinates cannot be found for either.
        """
        coords1 = cls.get_coordinates(pc1)
        coords2 = cls.get_coordinates(pc2)

        if not coords1 or not coords2:
            return None

        return cls.calculate_distance(coords1[0], coords1[1], coords2[0], coords2[1])
