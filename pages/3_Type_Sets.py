# pages/3_Type_Sets.py
import pandas as pd
import streamlit as st
from db import get_conn

st.header("Type Sets")

# ---------------------------
# Helpers
# ---------------------------
def table_exists(cx, name: str) -> bool:
    return cx.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,)
    ).fetchone() is not None

def view_exists(cx, name: str) -> bool:
    return table_exists(cx, name)

def list_type_sets():
    with get_conn() as cx:
        if not table_exists(cx, "type_set"):
            return []
        rows = cx.execute(
            "SELECT id, name, COALESCE(description,'') AS description FROM type_set ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]

def upsert_type_set(name: str, description: str = None, set_id: int | None = None) -> int:
    if not name:
        raise ValueError("Set name is required")
    with get_conn() as cx:
        if not table_exists(cx, "type_set"):
            raise RuntimeError("Missing table 'type_set'. Did you apply the Type Set schema patch?")
        if set_id:
            cx.execute("UPDATE type_set SET name=?, description=? WHERE id=?", (name, description, set_id))
            return set_id
        cur = cx.execute("INSERT INTO type_set(name, description) VALUES (?, ?)", (name, description))
        return cur.lastrowid

def list_series():
    with get_conn() as cx:
        rows = cx.execute("SELECT DISTINCT series FROM coin_master ORDER BY series").fetchall()
        return [r[0] for r in rows]

def find_coin_types(series: list[str] | None = None, years: tuple[int,int] | None = None,
                    proof_filter: str = "Any") -> list[dict]:
    sql = [
        "SELECT ct.id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety, ct.is_proof",
        "FROM coin_type ct",
        "JOIN coin_master cm ON cm.id = ct.master_id",
        "WHERE 1=1"
    ]
    params = []
    if series:
        placeholders = ",".join("?" for _ in series)
        sql.append(f"AND cm.series IN ({placeholders})")
        params.extend(series)
    if years:
        start, end = years
        sql.append("AND ct.year BETWEEN ? AND ?")
        params.extend([start, end])
    if proof_filter == "Proofs only":
        sql.append("AND ct.is_proof = 1")
    elif proof_filter == "Non-proof only":
        sql.append("AND (ct.is_proof IS NULL OR ct.is_proof = 0)")
    sql.append("ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety")
    with get_conn() as cx:
        rows = cx.execute("\n".join(sql), params).fetchall()
        return [dict(r) for r in rows]

def add_members(set_id: int, coin_type_ids: list[int]) -> int:
    if not coin_type_ids:
        return 0
    with get_conn() as cx:
        if not table_exists(cx, "type_set_member"):
            raise RuntimeError("Missing table 'type_set_member'. Did you apply the Type Set schema patch?")
        count = 0
        for cid in coin_type_ids:
            cx.execute(
                "INSERT OR IGNORE INTO type_set_member(set_id, coin_type_id) VALUES (?, ?)",
                (set_id, int(cid))
            )
            count += 1
        return count

def list_members(set_id: int) -> list[dict]:
    with get_conn() as cx:
        if not table_exists(cx, "type_set_member"):
            return []
        rows = cx.execute(
            """
            SELECT m.coin_type_id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety, ct.is_proof
            FROM type_set_member m
            JOIN coin_type ct ON ct.id = m.coin_type_id
            JOIN coin_master cm ON cm.id = ct.master_id
            WHERE m.set_id=?
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
            """,
            (set_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def remove_members(set_id: int, coin_type_ids: list[int]) -> int:
    if not coin_type_ids:
        return 0
    with get_conn() as cx:
        count = 0
        for cid in coin_type_ids:
            cx.execute("DELETE FROM type_set_member WHERE set_id=? AND coin_type_id=?", (set_id, int(cid)))
            count += 1
        return count

def choose_progress_view() -> str | None:
    with get_conn() as cx:
        if view_exists(cx, "v_type_set_progress_assign"):
            return "v_type_set_progress_assign"
        if view_exists(cx, "v_type_set_progress"):
            return "v_type_set_progress"
        return None

def get_progress_rows(set_id: int):
    view = choose_progress_view()
    if not view:
        return None, []
    with get_conn() as cx:
        rows = cx.execute(
            f"""
            SELECT * FROM {view}
            WHERE set_id=?
            ORDER BY series, year, mint_mark, variety
            """,
            (set_id,)
        ).fetchall()
        return view, [dict(r) for r in rows]

def derive_missing(df: pd.DataFrame) -> pd.DataFrame:
    # Try a set of possible indicator columns meaning 'have/on hand'
    candidate_cols = ["on_hand","have","have_count","have_qty","assigned_count","owned","has_any"]
    present = [c for c in candidate_cols if c in df.columns]
    if not present:
        return pd.DataFrame(columns=df.columns)
    col = present[0]
    s = pd.to_numeric(df[col], errors="coerce")
    if s.notna().any():
        mask = (s <= 0)
    else:
        mask = ~df[col].astype(bool)
    return df[mask].copy()

# Assignment helpers (optional; detected dynamically)
def list_assignments(set_id: int):
    with get_conn() as cx:
        if not (table_exists(cx, "type_set_assignment") and table_exists(cx, "specimen") and table_exists(cx, "lot")):
            return []
        rows = cx.execute(
            """
            SELECT a.coin_type_id AS coin_type_id, s.specimen_code AS specimen_code,
                   (s.sold_line_id IS NULL) AS on_hand
            FROM type_set_assignment a
            JOIN specimen s ON s.id = a.specimen_id
            JOIN lot l ON l.id = s.lot_id
            WHERE a.set_id = ?
            ORDER BY a.coin_type_id, s.specimen_code
            """,
            (set_id,)
        ).fetchall()
        return [dict(r) for r in rows]

def list_unassigned_specimens_for_type(coin_type_id: int, set_id: int):
    with get_conn() as cx:
        if not (table_exists(cx, "specimen") and table_exists(cx, "lot") and table_exists(cx, "type_set_assignment")):
            return []
        rows = cx.execute(
            """
            SELECT s.id, s.specimen_code
            FROM specimen s
            JOIN lot l ON l.id = s.lot_id
            WHERE l.coin_type_id = ?
              AND s.sold_line_id IS NULL
              AND NOT EXISTS (
                SELECT 1 FROM type_set_assignment a
                WHERE a.set_id = ? AND a.specimen_id = s.id
              )
            ORDER BY s.specimen_code
            """,
            (coin_type_id, set_id)
        ).fetchall()
        return [dict(r) for r in rows]

def assign_specimen(set_id: int, coin_type_id: int, specimen_id: int):
    with get_conn() as cx:
        cx.execute(
            "INSERT INTO type_set_assignment(set_id, coin_type_id, specimen_id) VALUES (?,?,?)",
            (set_id, coin_type_id, specimen_id)
        )

def unassign_specimen(set_id: int, specimen_code: str):
    with get_conn() as cx:
        row = cx.execute("SELECT id FROM specimen WHERE specimen_code = ?", (specimen_code,)).fetchone()
        if not row:
            return
        cx.execute("DELETE FROM type_set_assignment WHERE set_id = ? AND specimen_id = ?", (set_id, row[0]))

# ---------------------------
# UI
# ---------------------------
tab_my, tab_define = st.tabs(["My Sets", "Define / Catalog"])

# ======== My Sets ========
with tab_my:
    sets = list_type_sets()
    if not sets:
        st.info("No Type Sets yet. Use 'Define / Catalog' to create one.")
    else:
        options = {f"{s['name']} (#{s['id']})": s['id'] for s in sets}
        label = st.selectbox("Choose a Type Set", list(options.keys()), key="ts_pick")
        set_id = options[label]

        # Edit name/description
        ed_exp = st.expander("Edit set name/description")
        with ed_exp:
            sel = next(x for x in sets if x["id"] == set_id)
            new_name = st.text_input("Set name", value=sel["name"], key="ts_name_edit")
            new_desc = st.text_area("Description", value=sel.get("description",""), key="ts_desc_edit")
            if st.button("Save changes", key="ts_save_changes"):
                upsert_type_set(new_name, new_desc, set_id=set_id)
                st.success("Saved.")
                st.rerun()

        # Progress
        view_name, rows = get_progress_rows(set_id)
        if view_name is None:
            st.error("Required views not found. Ensure v_type_set_progress exists (and v_type_set_progress_assign optional).")
        else:
            st.caption(f"Using view: {view_name}")
            df_prog = pd.DataFrame(rows)
            st.subheader("Progress")
            st.dataframe(df_prog, use_container_width=True, hide_index=True)
            st.download_button(
                "Download Progress (CSV)",
                data=df_prog.to_csv(index=False).encode("utf-8"),
                file_name=f"type_set_{set_id}_progress.csv",
                mime="text/csv",
                key="csv_ts_progress",
            )

            # What's Missing
            df_missing = derive_missing(df_prog)
            st.subheader("What's Missing")
            if df_missing.empty:
                st.success("No missing items detected (or could not determine from available columns).")
            else:
                id_cols = [c for c in ["series","year","mint_mark","variety","coin_type_id"] if c in df_missing.columns]
                extra = [c for c in ["on_hand","have","have_count","have_qty","assigned_count","owned","has_any"] if c in df_missing.columns]
                disp = df_missing[id_cols + [c for c in extra if c not in id_cols]] if id_cols else df_missing
                st.dataframe(disp, use_container_width=True, hide_index=True)
                st.download_button(
                    "Download What's Missing (CSV)",
                    data=disp.to_csv(index=False).encode("utf-8"),
                    file_name=f"type_set_{set_id}_missing.csv",
                    mime="text/csv",
                    key="csv_ts_missing",
                )

        # Assign flips (if assignment/specimen tables exist)
        with get_conn() as cx:
            ok_assign = table_exists(cx, "type_set_assignment") and table_exists(cx, "specimen") and table_exists(cx, "lot")
        if ok_assign:
            st.subheader("Assign Flips to Set")
            if not df_prog.empty and "coin_type_id" in df_prog.columns:
                coin_rows = df_prog[["coin_type_id","series","year","mint_mark","variety"]].drop_duplicates()
                coin_rows["label"] = coin_rows.apply(
                    lambda r: f"{r['series']} {r['year']}{(' ' + r['mint_mark']) if r['mint_mark'] else ''}{(' • ' + r['variety']) if r['variety'] else ''} (#{r['coin_type_id']})",
                    axis=1
                )
                label_to_id = {r["label"]: int(r["coin_type_id"]) for _, r in coin_rows.iterrows()}
                pick_label = st.selectbox("Select coin type to assign a Flip ID to:", list(label_to_id.keys()), key="ts_pick_coin")
                coin_type_id = label_to_id[pick_label]

                candidates = list_unassigned_specimens_for_type(coin_type_id, set_id)
                if not candidates:
                    st.caption("No unassigned on-hand Flip IDs for this type.")
                else:
                    spec_map = {c["specimen_code"]: int(c["id"]) for c in candidates}
                    spec_label = st.selectbox("Choose Flip ID", list(spec_map.keys()), key="ts_pick_flip")
                    if st.button("Assign Flip to Set", key="ts_assign_flip"):
                        assign_specimen(set_id, coin_type_id, spec_map[spec_label])
                        st.success("Assigned.")
                        st.rerun()

                asn = list_assignments(set_id)
                if asn:
                    st.write("Current assignments for this set:")
                    df_asn = pd.DataFrame(asn)
                    st.dataframe(df_asn, use_container_width=True, hide_index=True)
                    to_unassign = st.selectbox("Unassign a Flip ID", options=[a["specimen_code"] for a in asn], key="ts_unas_pick")
                    if st.button("Unassign Flip", key="ts_unas_btn"):
                        unassign_specimen(set_id, to_unassign)
                        st.success("Unassigned.")
                        st.rerun()
            else:
                st.caption("No progress rows with coin_type_id to assign against.")

# ======== Define / Catalog ========
with tab_define:
    st.subheader("Create or edit a Type Set")
    left, right = st.columns(2)

    with left:
        sets = list_type_sets()
        mode = st.radio("Mode", ["Create new", "Edit existing"], horizontal=True, key="ts_mode")
        if mode == "Create new":
            new_name = st.text_input("Set name", key="ts_new_name")
            new_desc = st.text_area("Description", key="ts_new_desc")
            if st.button("Create set", key="ts_create_btn"):
                if not new_name:
                    st.error("Please enter a set name.")
                else:
                    sid = upsert_type_set(new_name, new_desc)
                    st.success(f"Created set #{sid}.")
                    st.rerun()
            work_set_id = None
        else:
            if not sets:
                st.info("No existing sets; switch to 'Create new'.")
                work_set_id = None
            else:
                options = {f"{s['name']} (#{s['id']})": s['id'] for s in sets}
                label = st.selectbox("Choose a set to edit", list(options.keys()), key="ts_edit_pick")
                work_set_id = options[label]
                sel = next(x for x in sets if x["id"] == work_set_id)
                e_name = st.text_input("Rename set", value=sel["name"], key="ts_edit_name")
                e_desc = st.text_area("Edit description", value=sel.get("description",""), key="ts_edit_desc")
                if st.button("Save set info", key="ts_save_info"):
                    upsert_type_set(e_name, e_desc, set_id=work_set_id)
                    st.success("Saved.")
                    st.rerun()

    with right:
        st.markdown("**Auto-build from catalog**")
        all_series = list_series()
        if not all_series:
            st.caption("No series found in catalog (coin_master). Add master records first.")
        else:
            sel_series = st.multiselect("Series", options=all_series, key="ts_auto_series")
            c1, c2, c3 = st.columns([1,1,1])
            start_year = c1.number_input("Start year", min_value=0, step=1, value=0, help="0 = no lower bound")
            end_year = c2.number_input("End year", min_value=0, step=1, value=0, help="0 = no upper bound")
            proof_filter = c3.selectbox("Proof filter", ["Any","Proofs only","Non-proof only"], index=0)
            years = None
            if start_year and end_year and end_year >= start_year:
                years = (int(start_year), int(end_year))
            elif start_year and not end_year:
                years = (int(start_year), 9999)
            elif end_year and not start_year:
                years = (0, int(end_year))
            preview = []
            if st.button("Preview matches", key="ts_preview_btn"):
                preview = find_coin_types(series=sel_series or None, years=years, proof_filter=proof_filter)
                if not preview:
                    st.info("No matches with those filters.")
            if preview:
                df_prev = pd.DataFrame(preview)
                df_prev["label"] = df_prev.apply(
                    lambda r: f"{r['series']} {r['year']}{(' ' + r['mint_mark']) if r['mint_mark'] else ''}{(' • ' + r['variety']) if r['variety'] else ''}"
                              + (" (Proof)" if r.get('is_proof') else ""),
                    axis=1
                )
                st.dataframe(df_prev[["id","label"]], use_container_width=True, hide_index=True)
                if mode == "Edit existing" and work_set_id:
                    if st.button("Add ALL previewed to set", key="ts_add_all_preview"):
                        add_members(work_set_id, [int(x["id"]) for x in preview])
                        st.success(f"Added {len(preview)} types to set.")
                        st.rerun()
                else:
                    st.caption("Switch to 'Edit existing' to add these to a specific set.")

        st.markdown("---")
        st.markdown("**Manual add/remove members**")
        if mode == "Edit existing" and work_set_id:
            # Manual add
            candidates = find_coin_types()
            if candidates:
                labels = {
                    f"{r['series']} {r['year']}{(' ' + r['mint_mark']) if r['mint_mark'] else ''}{(' • ' + r['variety']) if r['variety'] else ''} "
                    f"(#{r['id']}){' (Proof)' if r.get('is_proof') else ''}": int(r['id'])
                    for r in candidates
                }
                add_sel = st.multiselect("Add coin types", options=list(labels.keys()), key="ts_man_add")
                if st.button("Add selected", key="ts_man_add_btn"):
                    add_members(work_set_id, [labels[x] for x in add_sel])
                    st.success(f"Added {len(add_sel)} types.")
                    st.rerun()

            # Remove
            current = list_members(work_set_id)
            if current:
                labels_r = {
                    f"{r['series']} {r['year']}{(' ' + r['mint_mark']) if r['mint_mark'] else ''}{(' • ' + r['variety']) if r['variety'] else ''} "
                    f"(#{r['coin_type_id']}){' (Proof)' if r.get('is_proof') else ''}": int(r['coin_type_id'])
                    for r in current
                }
                rem_sel = st.multiselect("Remove coin types", options=list(labels_r.keys()), key="ts_man_rem")
                if st.button("Remove selected", key="ts_man_rem_btn"):
                    remove_members(work_set_id, [labels_r[x] for x in rem_sel])
                    st.success(f"Removed {len(rem_sel)} types.")
                    st.rerun()
        else:
            st.caption("Select 'Edit existing' and choose a set to manage members.")
