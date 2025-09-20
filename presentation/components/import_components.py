# presentation/components/import_components.py
import streamlit as st
import pandas as pd
from typing import Optional
from infrastructure.database.repositories.import_repository import ImportDataRepository
from presentation.components.helpers.import_helpers import (
    TransactionImporter, read_uploaded_file, prepare_master_data,
    prepare_type_data, build_column_mapping, get_template_info
)


class ImportRenderer:
    """UI rendering for import functions with dependency injection"""

    def __init__(self, repository: ImportDataRepository):
        self.repository = repository

    def render_quick_template_tab(self):
        """Render Quick Templates tab for transaction import"""
        st.subheader("⚡ Quick Templates (Transactions)")
        st.caption(
            "Upload the exact **coin_lines_template.csv** or **.xlsx** (headers must match).")

        uploaded = st.file_uploader("Upload template file", type=["csv", "xlsx", "xls"],
                                    key="qi_file")

        if uploaded is not None:
            df = read_uploaded_file(uploaded)

            st.write("**Preview**")
            st.dataframe(df.head(20), use_container_width=True)

            importer = TransactionImporter(df)

            if importer.validate_columns():
                dry_run = st.checkbox("Dry run (validate only—don't write)", value=True,
                                      key="qi_dryrun")

                if st.button("Validate & Import from Template", type="primary", key="qi_run"):
                    # Use the existing importer logic
                    importer.import_transactions(dry_run)

        with st.expander("Template Columns", expanded=False):
            template_info = get_template_info()
            st.markdown(f"""
            **Required**: {', '.join(f'`{col}`' for col in template_info['required'])}

            **Optional**: {', '.join(f'`{col}`' for col in template_info['optional'][:5])}...

            **Special Values:**
            - **asset_category**: {', '.join(f'**{v}**' for v in template_info['special_values']['asset_category'])}
            - **is_proof**: {', '.join(f'**{v}**' for v in template_info['special_values']['is_proof'])}
            - **valuation_method**: {', '.join(f'**{v}**' for v in template_info['special_values']['valuation_method'])}
            """)

    def render_flexible_import_tab(self):
        """Render Flexible Import tab with column mapper"""
        st.subheader("🧭 Flexible Import (Column Mapper)")
        st.caption("Upload any CSV/XLSX and map its columns to CoinApp **transaction** fields.")

        uploaded = st.file_uploader("Upload CSV/XLSX to map", type=["csv", "xlsx", "xls"],
                                    key="map_file")

        if uploaded is not None:
            src_df = read_uploaded_file(uploaded)

            st.write("**Preview**")
            st.dataframe(src_df.head(20), use_container_width=True)

            src_cols = ["(none)"] + list(src_df.columns)

            st.markdown("### Map Columns")
            maps = {}

            # Required fields
            st.markdown("#### Required Fields")
            cols = st.columns(2)
            for i, tgt in enumerate(TransactionImporter.REQUIRED_COLUMNS):
                maps[tgt] = cols[i % 2].selectbox(f"Required → {tgt}", src_cols,
                                                  key=f"map_req_{tgt}")

            # Optional fields
            st.markdown("#### Optional Fields")
            cols2 = st.columns(3)
            for i, tgt in enumerate(TransactionImporter.OPTIONAL_COLUMNS):
                maps[tgt] = cols2[i % 3].selectbox(f"Optional → {tgt}", src_cols, index=0,
                                                   key=f"map_opt_{tgt}")

            # Check for missing required mappings
            missing_req = [t for t in TransactionImporter.REQUIRED_COLUMNS if
                           maps.get(t) in (None, "(none)")]

            if missing_req:
                st.error("Please map all required fields: " + ", ".join(missing_req))
            else:
                dry_run = st.checkbox("Dry run (validate only—don't write)", value=True,
                                      key="map_dryrun")

                if st.button("Validate & Import Mapped File", type="primary", key="map_run"):
                    # Build mapped dataframe
                    mapped_df = pd.DataFrame()
                    for tgt in TransactionImporter.REQUIRED_COLUMNS + TransactionImporter.OPTIONAL_COLUMNS:
                        src = maps.get(tgt)
                        if not src or src == "(none)":
                            mapped_df[tgt] = None
                        else:
                            mapped_df[tgt] = src_df[src]

                    # Import using the mapped dataframe
                    importer = TransactionImporter(mapped_df)
                    importer.import_transactions(dry_run)

    def render_catalog_import_tab(self):
        """Render Catalog Import tab for masters and types"""
        st.subheader("📚 Catalog Import (Coin Masters & Coin Types)")
        st.caption("Add or update **catalog** without recording transactions.")

        # Coin Masters Import
        st.markdown("### Import Coin Masters")
        cm_file = st.file_uploader("Upload coin_master CSV/XLSX", type=["csv", "xlsx", "xls"],
                                   key="cm_up")

        if cm_file is not None:
            df = read_uploaded_file(cm_file)
            st.dataframe(df.head(20), use_container_width=True)

            # Validate data
            validation = self.repository.validate_master_data(df)

            if not validation.is_valid:
                st.error("Validation errors:")
                for error in validation.errors:
                    st.write(f"• {error}")
            else:
                if validation.warnings:
                    st.warning("Warnings:")
                    for warning in validation.warnings:
                        st.write(f"• {warning}")

                dry_run_cm = st.checkbox("Dry run (don't write)", value=True, key="cm_dry")

                if st.button("Import Masters", type="primary", key="cm_run"):
                    masters = prepare_master_data(df)
                    result = self.repository.import_coin_masters(masters, dry_run_cm)

                    if result.dry_run:
                        st.success(f"Dry run OK. Would upsert ~{result.created_count} masters.")
                    else:
                        if result.errors:
                            st.warning("Finished with issues:")
                            for error in result.errors[:10]:
                                st.write(f"• {error}")
                        st.success(f"Imported/updated {result.updated_count} masters.")

        st.markdown("---")

        # Coin Types Import
        st.markdown("### Import Coin Types")
        ct_file = st.file_uploader("Upload coin_type CSV/XLSX", type=["csv", "xlsx", "xls"],
                                   key="ct_up")

        if ct_file is not None:
            df = read_uploaded_file(ct_file)
            st.dataframe(df.head(20), use_container_width=True)

            # Validate data
            validation = self.repository.validate_type_data(df)

            if not validation.is_valid:
                st.error("Validation errors:")
                for error in validation.errors:
                    st.write(f"• {error}")
            else:
                if validation.warnings:
                    st.warning("Warnings:")
                    for warning in validation.warnings:
                        st.write(f"• {warning}")

                dry_run_ct = st.checkbox("Dry run (don't write)", value=True, key="ct_dry")

                if st.button("Import Types", type="primary", key="ct_run"):
                    types = prepare_type_data(df)
                    result = self.repository.import_coin_types(types, dry_run_ct)

                    if result.dry_run:
                        st.success(f"Dry run OK. Would upsert ~{result.created_count} coin types.")
                    else:
                        if result.errors:
                            st.warning("Finished with issues:")
                            for error in result.errors[:10]:
                                st.write(f"• {error}")
                        st.success(f"Imported/updated {result.created_count} coin types.")

    def render_import_help(self):
        """Render help section"""
        st.markdown("---")
        with st.expander("ℹ️ Import Help & Tips"):
            st.markdown("""
            ### Transaction Import Tips

            **is_proof column formats:**
            - Use `true/false`, `1/0`, `yes/no`, `y/n`, or `proof/business`
            - Case insensitive - "True", "TRUE", "proof", "PROOF" all work

            **Date formats:**
            - Use YYYY-MM-DD format (2023-12-25)
            - Excel dates are automatically converted

            **Required vs Optional:**
            - Required columns must be present and have values
            - Optional columns can be missing or empty
            - Missing optional columns are automatically added as blank

            **Master vs Types Import:**
            - Use **Masters** import for basic coin specifications (weight, metal, etc.)
            - Use **Types** import for specific years/varieties of existing masters
            - Use **Transactions** import to add coins to your inventory
            """)
