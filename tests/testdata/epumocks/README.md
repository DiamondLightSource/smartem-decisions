# EPU acquisition data intake

## Notes from Dan:

Attached is the approximate structure of metadata files written by the acquisition software with an example at each level.

All atlas data for a cassette is written into a directory with the data for different slots under `Sample*` directories.
In this case I’ve only included one example. The `Atlas.dm` file contains the grid square IDs and locations on the tile
images (that compose the atlas but I haven’t been able to capture some examples of thanks to a file system outage ahead
of electrical testing over the weekend). That information is quite buried.

The route to it is

```
AtlasSessionXml/Atlas/TilesEfficient/_items/TileXml/Nodes/KeyValuePairs/
(Something starting KeyValuePairOfintNodeXml followed by random characters)/value/b:PositionOnTheAtlas/c:Center
```

Under `EPU_session` I have put a few other metadata files that are produced for each EPU session.
In principle there may be multiple EPU sessions per atlas (i.e. per cassette slot),
but in practice it is often one-to-one.
The `EpuSession.dm` file contains the reference to the corresponding atlas under

EpuSessionXml / Samples / _items / SampleXml / AtlasId


```
$ tree tests/testdata/epumocks
tests/testdata/epumocks
├── Atlas
│   └── Supervisor_20240404_093820_Pete_Miriam_HexAuFoil
│       └── Sample4
│           └── Atlas
│               ├── Atlas.dm
│               └── Atlas.dm.xml
├── EPU_session
│   ├── EpuSession.dm
│   ├── EpuSession.dm.xml
│   ├── Images-Disc1
│   │   └── GridSquare_4590776
│   │       └── GridSquare_20240406_102420.xml
│   └── Metadata
│       └── GridSquare_20240406_102420.xml
├── GridSquare_4590776.dm
├── GridSquare_4590776.dm.xml
└── README.md
```
