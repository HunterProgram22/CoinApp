import pandas as pd

# Read both files
df_august = pd.read_csv('coin_transactions_thru_august.csv')
df_us_all = pd.read_excel('transactions_us_all.xlsx')


# Function to parse the master description
def parse_master_description(desc):
    if pd.isna(desc) or not isinstance(desc, str):
        return None, None

    # Remove country prefix
    desc = desc.strip()
    for prefix in ['US ', 'USA ', 'United States ']:
        if desc.startswith(prefix):
            desc = desc[len(prefix):]
            break

    # Split by ' - ' to separate denomination from series
    if ' - ' in desc:
        parts = desc.split(' - ', 1)
        denomination = parts[0].strip()
        series = parts[1].strip()
        return denomination, series

    # If no separator, return the whole thing as denomination
    return desc, None


# Get the Master Description column (3rd column, index 2)
master_descriptions = df_us_all.iloc[:, 2]

# Update the denomination and series columns
for i in range(min(len(df_august), len(master_descriptions))):
    master_desc = master_descriptions.iloc[i]
    denomination, series = parse_master_description(master_desc)

    if denomination is not None:
        df_august.loc[i, 'denomination'] = denomination
    if series is not None:
        df_august.loc[i, 'series'] = series

# Save the updated CSV
df_august.to_csv('coin_transactions_updated.csv', index=False)

print(f"✓ Processed {min(len(df_august), len(master_descriptions))} rows")
print("✓ File saved as: coin_transactions_updated.csv")