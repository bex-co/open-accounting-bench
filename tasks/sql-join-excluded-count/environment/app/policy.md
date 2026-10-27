# Join completeness (applies to this task)

- An INNER JOIN returns only rows that match in BOTH tables. Any
  payment whose vendor_id is absent from the vendor master is
  silently excluded from the result.
- Answer how many payment rows the query EXCLUDES.
