image_path=$@

gcloud ml vision detect-text "$image_path" > vision.json
time=$(jq -r '.responses[].textAnnotations[].description | select(test("^[0-9]+:[0-9]+:[0-9]+$"))' vision.json)

echo "VISION RESP '${time}'"

IFS=":" read -r hour minute second <<< "$time"

# Output the time with two characters for each section
printf -v image_time "%02d:%02d:%02d" "$hour" "$minute" "$second"
echo "$image_time"

# Add 12 to the hour and output the time
hour_plus_12=$((hour + 12))
printf -v image_time_plus_12 "%02d:%02d:%02d" "$hour_plus_12" "$minute" "$second"
echo "$image_time_plus_12"

echo "======"

dto_output=$( exiftool "$image_path" | grep "Date/Time Original" )

# Extract the time of the first line
file_time=$(echo "$dto_output" | grep 'Date/Time Original' | awk -F' ' '{print $5}' | head -n 1)

echo "EXIF"
echo "$file_time"

echo "======"

echo "${image_time}-${file_time}"
echo "${image_time_plus_12}-${file_time}"
