path=$1
folder=$(dirname "$path")

ogr2ogr -f gpkg "${folder}/editing.gpkg" "$path" waypoints routes track_points
