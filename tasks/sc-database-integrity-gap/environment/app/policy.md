# Database integrity (applies to this task)

- Entity integrity: every table needs a primary key whose value is
  unique and never null; duplicate key values violate it.
- Referential integrity: a foreign key must be enforced by a
  declared constraint so referenced values must exist in the
  referenced table. Merely having a reference-shaped column does
  not enforce anything.
- Normalization (first normal form): repeating groups (the same
  fact stored in numbered columns like phone_1, phone_2) violate it.
- A nullable column for a genuinely optional attribute is not, by
  itself, an integrity violation.
