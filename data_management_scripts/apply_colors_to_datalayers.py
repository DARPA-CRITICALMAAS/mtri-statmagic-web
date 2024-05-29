import dm_util


# Colors retrieved from here:
# https://colorbrewer2.org/#type=qualitative&scheme=Paired&n=12
#
# (skipping the paler colors b/c they don't show enough contrast)
colors = [
    #[166, 206, 227],
    [31, 120, 180],
    #[178, 223, 138],
    [51, 160, 44],
   # [251, 154, 153],
    [227, 26, 28],
    #[253, 191, 111],
    [255, 127, 0],
   # [202, 178, 214],
    [106, 61, 154],
   # [255, 255, 153],
    [177, 89, 40],
]

for i,d in enumerate(dm_util.getDataLayers()):
    color = colors[i % len(colors)]
    #if not d.color:
    d.color = ','.join([str(c) for c in color])
    d.save()