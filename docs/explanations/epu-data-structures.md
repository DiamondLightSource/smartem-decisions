# EPU Output Directory Structure

> Directory layout on the EPU machine will differ from the layout of that
> same directory synced to file storage. Layout relevant to epu data intake component
> is as it appears on the EPU machines, where the watcher runs.

In a user visit there can be more than one `EpuSession.dm` and more than one "project dir"
as there will be one for each grid. We usually treat each `EpuSession.dm` independently,
but they all connect to the same atlas.

```
grid-data-dir-structure-example
├── EpuSession.dm
├── Images-Disc1
│  ├── GridSquare_8999138
│  │  ├── Data
│  │  │  ├── FoilHole_9015883_Data_9017347_6_20250108_154915.jpg
│  │  │  ├── FoilHole_9015883_Data_9017347_6_20250108_154915.xml
│  │  │  ├── FoilHole_9015883_Data_9017354_6_20250108_154918.jpg
│  │  │  └── FoilHole_9015883_Data_9017354_6_20250108_154918.xml
│  │  ├── FoilHoles
│  │  │  ├── FoilHole_9015889_20250108_154715.jpg
│  │  │  ├── FoilHole_9015889_20250108_154715.xml
│  │  │  ├── FoilHole_9015889_20250108_154725.jpg
│  │  │  └── FoilHole_9015889_20250108_154725.xml
│  │  ├── GridSquare_20250108_151151.jpg
│  │  └── GridSquare_20250108_151151.xml
│  └── GridSquare_8999186
│      ├── Data
│      │  ├── FoilHole_9028219_Data_9017347_50_20250109_062621.jpg
│      │  ├── FoilHole_9028219_Data_9017347_50_20250109_062621.xml
│      │  ├── FoilHole_9028219_Data_9017354_50_20250109_062624.jpg
│      │  └── FoilHole_9028219_Data_9017354_50_20250109_062624.xml
│      ├── FoilHoles
│      │  ├── FoilHole_9028276_20250109_061712.jpg
│      │  ├── FoilHole_9028276_20250109_061712.xml
│      │  ├── FoilHole_9028276_20250109_061722.jpg
│      │  ├── FoilHole_9028276_20250109_061722.xml
│      │  └── FoilHole_9028325_20250109_063110.jpg
│      ├── GridSquare_20250108_152955.jpg
│      └── GridSquare_20250108_152955.xml
└── Metadata
    ├── GridSquare_8999138.dm
    └── GridSquare_8999186.dm
```

## EPU Directory Structure Details

- An EPU directory consists of multiple subdirectories as well as `.xml`, `.dm` and `.jpg` files
  - Any `.dm` files are actually XML files
  - This directory is written to incrementally by EPU software, it does not materialise in a complete state right away
- An EPU directory will contain a file named `EpuSession.dm` at root level. Useful information contained in this file:
  - Session _name_, _id_ and _start time_;
  - fs path of the EPU directory;
  - A reference to `Atlas.dm` file (which resides outside the EPU directory);
  - _clustering_ mode and radius
- An `Atlas.dm` file contains general information about the acquisition session (which possibly duplicates info already
  found in `EpuSession.dm` and, crucially, information about _atlas tiles_
  - _Atlas tiles_ contain positioning information, which is needed to map physical positions on the grid (measured in
    number of turns of the actuator) to their pixel coordinates in image files
- An EPU directory will contain a subdirectory named `Metadata/` at root level
  - `Metadata` directory is flat and contains a large list of files all using a naming convention
    `GridSquare_<gridsquare_id>.dm`, for example: `GridSquare_8999138.dm`, `GridSquare_8999186.dm`
  - The `Metadata/` directory contains all grid squares not just the ones that are captured
  - Some `Metadata/GridSquare_<gridsquare_id>.dm` files will have a significantly larger file size than others.
    Those are the ones that were of interest and so further scans took place during the acquisition session
  - The rest of GridSquare files under `Metadata/` are typically around 2.8Kb in size
- An EPU directory contains at least one subdirectory named `Images-Disc1/` at root level,
  and it's possible to have multiple subdirectories with a naming convention `Images-Disc<int>`, though in most
  cases there will only be one.
  - An `Images-Disc<int>/` directory will contain a number of subdirectories following a naming convention
    `GridSquare_<gridsquare_id>/`, corresponding to GridSquare files in `Metadata/`, but only for GridSquares of
    interest where further scanning took place
- A GridSquare directory matching a glob `Images-Disc<int>/GridSquare_<gridsquare_id>/` will contain:
  - a GridSquare manifest file, such as `GridSquare_20250108_152955.xml`
  - **optionally** subdirectories `FoilHoles/` and `Data/`, containing FoilHole and Micrograph information, respectively
