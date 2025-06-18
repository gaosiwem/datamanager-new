import re
import logging

logger = logging.getLogger(__name__)

class CoordinateUtils:
    @staticmethod
    def _dms_to_decimal(degrees, minutes, seconds, direction):
        decimal = float(degrees) + float(minutes) / 60
        if seconds:
            decimal += float(seconds) / 3600
        if direction.upper() in ['S', 'W']:
            decimal = -abs(decimal)
        return decimal

    @staticmethod
    def _apply_direction_to_decimal(value, direction):
        decimal = float(value)
        if direction and direction.upper() in ['S', 'W']:
            decimal = -abs(decimal)
        return decimal

    @staticmethod
    def _attempt_decimal_correction(value, max_abs_range):
        """
        Attempts to correct a decimal value that is significantly out of range
        by assuming a missing decimal point.
        Returns corrected value and a boolean indicating if correction occurred.
        """
        original_value = value
        # Only attempt correction if the value is significantly out of range
        if abs(original_value) > max_abs_range and abs(original_value) > max_abs_range * 10:
            # Common missing decimal scenarios for lat/lon precision (e.g., 5-7 decimal places)
            for divisor_power in [5, 6, 7]:
                attempted_value = original_value / (10**divisor_power)
                if abs(attempted_value) <= max_abs_range:
                    logger.info(f"Heuristic correction applied: '{original_value}' -> '{attempted_value}' (divided by 10^{divisor_power} for missing decimal point).")
                    return attempted_value, True
        return original_value, False

    @staticmethod
    def _parse_dms_part(dms_str):
        dms_regex_standard = re.compile(
            r"""(?P<deg>\d{1,3})°?\s*
                (?P<min>\d{1,2})['′]?\s*
                (?:(?P<sec>\d{1,2}(?:\.\d+)?)["″])?\s*
                (?P<dir>[NSEW])?""",
            re.VERBOSE | re.IGNORECASE
        )
        dms_regex_dir_first = re.compile(
            r"""(?P<dir>[NSEW])\s*
                (?P<deg>\d{1,3})\s*
                (?P<min>\d{1,2})['′]?\s*
                (?:(?P<sec>\d{1,2}(?:\.\d+)?)["″])?""",
            re.VERBOSE | re.IGNORECASE
        )

        match = dms_regex_standard.match(dms_str.strip())
        if not match:
            match = dms_regex_dir_first.match(dms_str.strip())

        if not match:
            raise ValueError(f"Unrecognized DMS part format: {dms_str}")

        deg = match.group('deg')
        min_ = match.group('min')
        sec = match.group('sec')
        dir_ = match.group('dir') or ''

        if int(deg) > 180 or (dir_.upper() in ['N', 'S'] and int(deg) > 90):
            raise ValueError(f"Degree value {deg} out of valid range for DMS part: {dms_str}")
        if min_ and int(min_) >= 60:
             raise ValueError(f"Minutes value {min_} out of valid range (0-59) for DMS part: {dms_str}")
        if sec and float(sec) >= 60:
             raise ValueError(f"Seconds value {sec} out of valid range (0-59.999) for DMS part: {dms_str}")

        return CoordinateUtils._dms_to_decimal(deg, min_, sec, dir_)

    @staticmethod
    def parse_coordinate(coordinate_str):
        coordinate_str = coordinate_str.strip()

        # NEW: Try "Latitude: X. Longitude: Y" or "Latitude: DMS_X. Longitude: DMS_Y" format
        # This regex broadly captures the parts between the labels
        labeled_pair_match = re.match(
            r'Latitude:\s*(.+?)\.?\s*Longitude:\s*(.+?)$',
            coordinate_str, re.IGNORECASE | re.DOTALL # DOTALL allows matching across newlines if any
        )
        if labeled_pair_match:
            lat_part_str = labeled_pair_match.group(1).strip()
            lon_part_str = labeled_pair_match.group(2).strip()

            lat = None
            lon = None

            # Attempt to parse lat_part_str and lon_part_str as either Decimal or DMS
            try:
                # Try as Decimal Degrees first
                lat = float(lat_part_str)
                lon = float(lon_part_str)
                # Apply heuristic correction for significantly out-of-range values
                lat, _ = CoordinateUtils._attempt_decimal_correction(lat, 90.0)
                lon, _ = CoordinateUtils._attempt_decimal_correction(lon, 180.0)
            except ValueError:
                try:
                    # If not decimal, try as DMS parts
                    lat = CoordinateUtils._parse_dms_part(lat_part_str)
                    lon = CoordinateUtils._parse_dms_part(lon_part_str)
                    # Apply heuristic correction to DMS conversion results (less common but possible)
                    lat, _ = CoordinateUtils._attempt_decimal_correction(lat, 90.0)
                    lon, _ = CoordinateUtils._attempt_decimal_correction(lon, 180.0)
                except ValueError:
                    # If neither decimal nor DMS parsing works for labeled parts
                    raise ValueError(f"Could not parse labeled coordinate parts '{lat_part_str}' and '{lon_part_str}'.")

            # Final validation after parsing and potential correction
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"Coordinate values out of valid range even after heuristic: Lat {lat}, Lon {lon}")
            return {"latitude": lat, "longitude": lon}


        # 1. Try Decimal Degrees (e.g., -25.783975, 28.140278) - NO DIRECTION SUFFIX
        dec_match = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*[,;/\s]+\s*(-?\d+(?:\.\d+)?)\s*$", coordinate_str)
        if dec_match:
            lat = float(dec_match.group(1))
            lon = float(dec_match.group(2))

            # Apply heuristic correction for significantly out-of-range values
            lat, _ = CoordinateUtils._attempt_decimal_correction(lat, 90.0)
            lon, _ = CoordinateUtils._attempt_decimal_correction(lon, 180.0)

            # Validate ranges after potential correction
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"Coordinate values out of valid range even after heuristic: Lat {lat}, Lon {lon}")

            return {"latitude": lat, "longitude": lon}

        # 2. Try Decimal Degrees WITH Direction Suffix (e.g., 25.7379 S, 28.2028 E)
        dec_dir_match = re.match(
            r"^(-?\d+(?:\.\d+)?)\s*(?P<lat_dir>[NSEW])?\s*"
            r"(?:,\s*|\s+)"
            r"(-?\d+(?:\.\d+)?)\s*(?P<lon_dir>[NSEW])?$",
            coordinate_str, re.IGNORECASE
        )
        if dec_dir_match:
            lat_val = dec_dir_match.group(1)
            lat_dir = dec_dir_match.group('lat_dir')
            lon_val = dec_dir_match.group(3)
            lon_dir = dec_dir_match.group('lon_dir')

            lat = CoordinateUtils._apply_direction_to_decimal(lat_val, lat_dir)
            lon = CoordinateUtils._apply_direction_to_decimal(lon_val, lon_dir)

            # Apply heuristic correction
            lat, _ = CoordinateUtils._attempt_decimal_correction(lat, 90.0)
            lon, _ = CoordinateUtils._attempt_decimal_correction(lon, 180.0)

            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError(f"Coordinate values out of valid range even after heuristic: Lat {lat}, Lon {lon}")

            return {"latitude": lat, "longitude": lon}


        # 3. Try DMS format (e.g., 30°33'34.2S 17°59'23.3"E or S26 19'31.74551 28 14'30"E)
        dms_space_separated_match = re.match(r'(.+?)\s+(.+)', coordinate_str)
        if dms_space_separated_match:
            try:
                lat_str = dms_space_separated_match.group(1).strip()
                lon_str = dms_space_separated_match.group(2).strip()
                lat = CoordinateUtils._parse_dms_part(lat_str)
                lon = CoordinateUtils._parse_dms_part(lon_str)

                # Apply heuristic correction
                lat, _ = CoordinateUtils._attempt_decimal_correction(lat, 90.0)
                lon, _ = CoordinateUtils._attempt_decimal_correction(lon, 180.0)


                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(f"Coordinate values out of valid range even after heuristic: Lat {lat}, Lon {lon}")

                return {"latitude": lat, "longitude": lon}
            except ValueError:
                pass


        # 4. Try parsing as two CONCATENATED DMS parts (e.g., 'S26 19\'31.74551E318\'29.43339')
        concatenated_dms_match = re.match(
            r"(?P<lat_dir>[NSEW])(?P<lat_deg>\d{1,3})\s*(?P<lat_min>\d{1,2})['′]?\s*(?:(?P<lat_sec>\d{1,2}(?:\.\d+)?)[\"″])?\s*"
            r"(?P<lon_dir>[NSEW])(?P<lon_deg>\d{1,3})['°\s]*\s*(?P<lon_min>\d{1,2})['′]?\s*(?:(?P<lon_sec>\d{1,2}(?:\.\d+)?)[\"″])?",
            coordinate_str, re.IGNORECASE
        )
        if concatenated_dms_match:
            try:
                lat = CoordinateUtils._dms_to_decimal(
                    concatenated_dms_match.group('lat_deg'),
                    concatenated_dms_match.group('lat_min'),
                    concatenated_dms_match.group('lat_sec'),
                    concatenated_dms_match.group('lat_dir')
                )
                lon = CoordinateUtils._dms_to_decimal(
                    concatenated_dms_match.group('lon_deg'),
                    concatenated_dms_match.group('lon_min'),
                    concatenated_dms_match.group('lon_sec'),
                    concatenated_dms_match.group('lon_dir')
                )
                # Apply heuristic correction
                lat, _ = CoordinateUtils._attempt_decimal_correction(lat, 90.0)
                lon, _ = CoordinateUtils._attempt_decimal_correction(lon, 180.0)

                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(f"Coordinate values out of valid range even after heuristic: Lat {lat}, Lon {lon}")
                return {"latitude": lat, "longitude": lon}
            except ValueError as e:
                logger.debug(f"Concatenated DMS parsing failed: {e}")
                pass

        raise ValueError(f"Input does not match any recognized coordinate format.")

    @staticmethod
    def clean_coordinates(raw_coordinate_string):
        cleaned_coordinates = []
        raw = raw_coordinate_string.strip()
        raw_lower = raw.lower()

        list_of_potential_coords = []

        # 1. Check for " and " separator
        if ' and ' in raw_lower:
            list_of_potential_coords = re.split(r'\s+and\s+', raw, flags=re.IGNORECASE)
        # 2. Check for multiple "Latitude:" prefixes (indicating multiple concatenated blocks)
        elif raw_lower.count('latitude:') > 1:
            # Split by "Latitude: " and reconstruct the full coordinate strings
            parts = re.split(r'(latitude:\s*)', raw, flags=re.IGNORECASE)
            reconstructed_coords = []
            for i in range(1, len(parts), 2): # Iterate through 'Latitude: ' chunks
                if i + 1 < len(parts):
                    # Combine "Latitude: " prefix with its content block
                    reconstructed_coords.append(parts[i] + parts[i+1])
            list_of_potential_coords = reconstructed_coords
        else:
            # If neither multi-"and" nor multi-"Latitude:" pattern, treat as single coordinate string
            list_of_potential_coords.append(raw)

        for coord_str in list_of_potential_coords:
            coord_str = coord_str.strip()
            if not coord_str:
                continue
            try:
                parsed_coord = CoordinateUtils.parse_coordinate(coord_str)
                cleaned_coordinates.append(parsed_coord)
            except ValueError as e:
                error_msg = str(e)
                if error_msg.startswith("Coordinate values out of valid range:"):
                    logger.warning(f"Failed to parse coordinate '{coord_str}': {error_msg}")
                elif error_msg.startswith("Input does not match any recognized coordinate format."):
                    logger.warning(f"Failed to parse coordinate '{coord_str}': Input format unrecognized.")
                elif error_msg.startswith("Unrecognized DMS part format:"):
                     logger.warning(f"Failed to parse coordinate '{coord_str}': DMS part format unrecognized.")
                elif error_msg.startswith("Could not parse labeled coordinate parts"):
                     logger.warning(f"Failed to parse coordinate '{coord_str}': {error_msg}")
                elif error_msg.startswith("Coordinate values out of valid range even after heuristic:"):
                     logger.warning(f"Failed to parse coordinate '{coord_str}': {error_msg}")
                else:
                    logger.warning(f"Failed to parse coordinate '{coord_str}': {error_msg}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while parsing coordinate '{coord_str}': {e}", exc_info=True)
        return cleaned_coordinates

# Configure logging (set level to INFO to see heuristic corrections)
logging.basicConfig(level=logging.INFO)