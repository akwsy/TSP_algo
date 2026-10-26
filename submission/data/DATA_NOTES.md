# Generated scenario data

Geographic source: supplied GeoNames MY.txt. Original rows retain all 19 columns.
https://www.geonames.org/ ; source metadata states CC BY 4.0:
https://creativecommons.org/licenses/by/4.0/
Geographic records are supplied as-is, without accuracy guarantees.

Selection: 10 vertices including depot 1735161; 9 potential customers.
Customer filters: feature class P, admin1 14.
Method: population; seed 42. The explicit depot bypasses customer filters.
Population selection sorts by descending population, then ID; random selection shuffles ID-sorted candidates.
Selection settings are recorded in scenario.properties. No source-device path is stored.

SIMULATION: Haversine distances, Earth radius 6371.0088 km; constant 40.0 km/h; origin 08:00; zero service time.
Windows use a shuffled reference route with the same seed and +/-30.0 minutes slack (openings clipped to zero). They are not real appointments.
The reference witness satisfies customer windows but may exceed the period. Neither solver reads it.
Trip period: 120.0 minutes including waiting and return.
Maximize customer visits; shorter distance breaks equal-count ties.
Regeneration replaces these scenario files and resets their settings/windows to the command's options.
