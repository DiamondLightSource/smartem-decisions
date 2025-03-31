# Misc tools

## Format XML to make it readable, recursively

```bash
# To reformat all `.xml` and `.dm` files in a given directory recursively, rewriting in-place
# from single-line to human-readable:
python tools/format_xml.py <some_dir> -r

# Multiple dirs:
python tools/format_xml.py -r \
  ../smartem-decisions-test-datasets/metadata_Supervisor_20250114_220855_23_epuBSAd20_GrOxDDM \
  ../smartem-decisions-test-datasets/metadata_Supervisor_20241220_140307_72_et2_gangshun \
  ../smartem-decisions-test-datasets/metadata_Supervisor_20250108_101446_62_cm40593-1_EPU

# For more options see:
python tools/format_xml.py --help
```

## Find all foilhole manifest duplicates in a directory, recursively

```bash
 
tools/find_foilhole_duplicates.py --help
# e.g.
tools/find_foilhole_duplicates.py ./tests/testdata/bi37708-28
```

## List all files matching glob recursively in descending order by file size:

```bash
# To find 
rg --files -g 'GridSquare_*.dm' ./tests/testdata/bi37708-28 \
  | xargs -d '\n' ls -lh | sort -k5 -rn | awk '{print $9, $5}'
```
