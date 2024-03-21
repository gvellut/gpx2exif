path=$1
folder=$(dirname "$path")

ogr2ogr -f GPX "${folder}/corrected.gpx" "$1" track_points -dsco GPX_USE_EXTENSIONS=YES -skipfailures