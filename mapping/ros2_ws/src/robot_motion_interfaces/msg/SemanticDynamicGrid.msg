# Custom Semantic-Dynamic Grid
#
# -1 : Unknown / Unobserved
#  0 : Observed Free
#  1+ : Semantic Class
#
# encoded_value = class_id + 1
#
# ex)
# person: class_id=0 -> grid value=1

std_msgs/Header header

nav_msgs/MapMetaData info

int16[] data
