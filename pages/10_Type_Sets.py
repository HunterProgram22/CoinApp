# pages/10_Type_Sets.py
import streamlit as st
import pandas as pd
import sqlite3
from db import get_conn

st.header("📚 Type Sets")

# ------------------------ DB helpers ------------------------
def list_sets():
    with get_conn() as cx:
        rows = cx.execute("SELECT id, name, description, mode, created_at FROM type_set ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

def create_set(name: str, description: str, mode: str) -> int:
    with get_conn() as cx:
        cur = cx.execute("INSERT INTO type_set(name, description, mode) VALUES (?,?,?)",
                         (name.strip(), description or None, mode))
        return cur.lastrowid

def add_item(set_id: int, coin_type_id: int, required_qty: int = 1):
    with get_conn() as cx:
        cx.execute("""INSERT OR REPLACE INTO type_set_item(set_id, coin_type_id, required_qty)
                      VALUES (?,?,?)""", (set_id, coin_type_id, int(required_qty)))

def add_rule(set_id: int, **kw):
    cols = ["set_id"]; vals = [set_id]
    for c in ["country","denomination","series","is_proof","mint_mark_in","year_min","year_max","year_list","variety_like"]:
        v = kw.get(c, None)
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        cols.append(c); vals.append(v)
    ph = ",".join(["?"]*len(vals))
    with get_conn() as cx:
        cx.execute(f"INSERT INTO type_set_rule({','.join(cols)}) VALUES ({ph})", vals)

def get_progress(set_id: int, with_assign=False):
    view = "v_type_set_progress_assign" if with_assign else "v_type_set_progress"
    with get_conn() as cx:
        rows = cx.execute(f"""
            SELECT * FROM {view}
             WHERE set_id=?
             ORDER BY series, year, mint_mark, variety
        """, (set_id,)).fetchall()
        return [dict(r) for r in rows]

def list_series():
    with get_conn() as cx:
        rows = cx.execute("SELECT DISTINCT series FROM coin_master ORDER BY series").fetchall()
        return [r["series"] for r in rows]

def list_coin_types_for_picker():
    with get_conn() as cx:
        rows = cx.execute(
            """
            SELECT ct.id,
                   cm.country, cm.denomination, cm.series,
                   ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety, ct.is_proof
            FROM coin_type ct JOIN coin_master cm ON cm.id = ct.master_id
            ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
            """
        ).fetchall()
        labels = []
        ids = []
        for r in rows:
            mm = (r["mint_mark"] or "").strip()
            var = (r["variety"] or "").strip()
            proof = " PR" if r["is_proof"] else ""
            lab = f"{r['series']} {r['year']}{(' ' + mm) if mm else ''}{(' • ' + var) if var else ''}{proof}  (#{r['id']})"
            labels.append(lab); ids.append(r["id"])
        return labels, ids

def list_specimens_for_type_on_hand(coin_type_id: int):
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT code FROM specimen
             WHERE coin_type_id=? AND (sold_line_id IS NULL)
             ORDER BY code
        """, (coin_type_id,)).fetchall()
        return [r["code"] for r in rows]

def list_assignments(set_id: int):
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT coin_type_id, specimen_code, (sold_line_id IS NULL) AS on_hand
            FROM type_set_fulfillment f
            JOIN specimen s ON s.code = f.specimen_code
            WHERE f.set_id=?
        """, (set_id,)).fetchall()
        return [dict(r) for r in rows]

def assign_specimens(set_id: int, coin_type_id: int, codes: list[str]):
    inserted = 0
    errs = []
    with get_conn() as cx:
        for code in codes:
            code = code.strip().upper()
            row = cx.execute("""
                SELECT code FROM specimen
                 WHERE code=? AND coin_type_id=? AND sold_line_id IS NULL
            """, (code, coin_type_id)).fetchone()
            if not row:
                errs.append(f"{code}: not found, wrong type, or not on-hand")
                continue
            try:
                cx.execute("""
                    INSERT INTO type_set_fulfillment(set_id, coin_type_id, specimen_code)
                    VALUES (?,?,?)
                """, (set_id, coin_type_id, code))
                inserted += 1
            except Exception as e:
                errs.append(f"{code}: {e}")
    return inserted, errs

def unassign_specimens(set_id: int, codes: list[str]):
    removed = 0
    with get_conn() as cx:
        for code in codes:
            cx.execute("DELETE FROM type_set_fulfillment WHERE set_id=? AND specimen_code=?", (set_id, code))
            removed += cx.total_changes
    return removed

def build_missing_df(set_id: int):
    rows = get_progress(set_id, with_assign=True)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["assigned_onhand_qty"] = df.get("assigned_onhand_qty", 0).fillna(0)
    df["have_qty"] = df["have_qty"].fillna(0)
    df["missing_qty"] = (df["required_qty"] - df[["assigned_onhand_qty","have_qty"]].max(axis=1)).clip(lower=0)
    df = df.rename(columns={
        "series":"Series","year":"Year","mint_mark":"Mint Mark","variety":"Variety",
        "is_proof":"Proof","required_qty":"Required","have_qty":"On Hand",
        "assigned_onhand_qty":"Assigned (on hand)","assigned_codes_csv":"Assigned Codes",
        "missing_qty":"Missing"
    })
    return df

# ------------------------ UI ------------------------
tab_browse, tab_new, tab_manage = st.tabs(["My Sets", "New Set", "Manage"])

# ---- My Sets (progress + assignments + shopping list) ----
with tab_browse:
    sets_ = list_sets()
    if not sets_:
        st.info("No Type Sets yet. Create one in the 'New Set' tab.")
    else:
        name_to_id = {f"{s['name']} [{s['mode']}]" : s["id"] for s in sets_}
        sel_name = st.selectbox("Select a set", list(name_to_id.keys()))
        set_id = name_to_id[sel_name]

        try:
            rows = get_progress(set_id, with_assign=True)
        except sqlite3.OperationalError as e:
            st.error("Type Sets schema isn't fully installed. Apply the patch file below, then refresh.")
            st.markdown("**Patch:** [schema_typesets_fix.sql](sandbox:/mnt/data/schema_typesets_fix.sql)")
            st.code("sqlite3 data\coinapp.sqlite < schema_typesets_fix.sql", language="bat")
            st.stop()

        total = len(rows)
        done_auto = sum(1 for r in rows if r.get("is_complete") == 1)
        done_assn = sum(1 for r in rows if r.get("is_complete_by_assignment") == 1)

        colA, colB = st.columns(2)
        colA.metric("Auto Progress (by on-hand qty)", f"{done_auto}/{total}")
        colB.metric("Assigned Progress (by Flip IDs)", f"{done_assn}/{total}")

        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                "series":"Series","year":"Year","mint_mark":"Mint Mark","variety":"Variety",
                "is_proof":"Proof","required_qty":"Required","have_qty":"On Hand",
                "assigned_onhand_qty":"Assigned (on hand)","assigned_codes_csv":"Assigned Codes"
            })
            if "Assigned Codes" in df.columns:
                df["Assigned Codes"] = df["Assigned Codes"].fillna("").apply(lambda s: ", ".join([c for c in str(s).split(",") if c]))
            show_cols = [c for c in ["Series","Year","Mint Mark","Variety","Proof","Required","On Hand","Assigned (on hand)","Assigned Codes"] if c in df.columns]
            st.dataframe(df[show_cols], use_container_width=True)

        st.subheader("🛒 What's Missing — Shopping List")
        miss_df = build_missing_df(set_id)
        if miss_df.empty or miss_df["Missing"].sum() == 0:
            st.success("Nothing missing—nice!")
        else:
            tbl = miss_df[miss_df["Missing"] > 0][["Series","Year","Mint Mark","Variety","Proof","Required","On Hand","Assigned (on hand)","Missing"]]
            st.dataframe(tbl, use_container_width=True)
            out = miss_df[miss_df["Missing"] > 0][["Series","Year","Mint Mark","Variety","Proof","Missing"]].to_csv(index=False).encode("utf-8")
            st.download_button("Download shopping list CSV", out, file_name=f"type_set_shopping_list_{set_id}.csv", mime="text/csv")

        st.divider()
        st.subheader("Assign / Unassign Flip IDs")
        if rows:
            label_map = {}
            for r in rows:
                disp = f"{r['series']} {r['year']}{(' ' + r['mint_mark']) if r['mint_mark'] else ''}{(' • ' + r['variety']) if r['variety'] else ''}"
                label_map[disp] = r["coin_type_id"]
            pick_label = st.selectbox("Coin Type", list(label_map.keys()))
            coin_type_id = label_map[pick_label]

            avail = list_specimens_for_type_on_hand(coin_type_id)
            asn_rows = [a for a in list_assignments(set_id) if a["coin_type_id"] == coin_type_id]
            assigned_codes = [a["specimen_code"] + ("" if a["on_hand"] else " (sold)") for a in asn_rows]
            st.caption("Assigned codes: " + (", ".join(assigned_codes) if assigned_codes else "—"))

            col1, col2 = st.columns(2)
            with col1:
                picks = st.multiselect("Flip IDs to **assign**", avail, help="Only on-hand specimens of this type appear here.")
                if st.button("Assign selected"):
                    if not picks:
                        st.warning("Pick at least one Flip ID.")
                    else:
                        added, errs = assign_specimens(set_id, coin_type_id, picks)
                        if added: st.success(f"Assigned {added} Flip ID(s).")
                        if errs:
                            st.warning("Some items could not be assigned:")
                            for e in errs[:50]: st.write("•", e)
                        st.experimental_rerun()
            with col2:
                to_remove = st.multiselect("Flip IDs to **unassign**", [a["specimen_code"] for a in asn_rows])
                if st.button("Unassign selected"):
                    if not to_remove:
                        st.warning("Pick at least one Flip ID to unassign.")
                    else:
                        removed = unassign_specimens(set_id, to_remove)
                        st.success(f"Unassigned {removed} Flip ID(s).")
                        st.experimental_rerun()

# ---- New Set ----
with tab_new:
    mode = st.radio("Mode", ["RULES","MANUAL"], horizontal=True, help="RULES = auto-populate by filters; MANUAL = pick exact coin types")
    name = st.text_input("Set name")
    desc = st.text_input("Description", placeholder="Optional")

    if mode == "RULES":
        st.subheader("Rule filters")
        col1, col2, col3 = st.columns(3)
        series = col1.selectbox("Series", ["(any)"] + list_series())
        is_proof = col2.selectbox("Proof?", ["(any)","Business (0)","Proof (1)"])
        mint_csv = col3.text_input("Mint marks (CSV)", placeholder="e.g., S,D,W")

        col4, col5 = st.columns(2)
        year_min = col4.number_input("Year min", min_value=0, step=1, value=0)
        year_max = col5.number_input("Year max", min_value=0, step=1, value=0)
        year_list = st.text_input("Year list (CSV)", placeholder="e.g., 1980,1982,2015,2016")
        variety_like = st.text_input("Variety LIKE (SQL)", placeholder="e.g., %Type 1%")

        if st.button("Preview matches"):
            where = ["1=1"]
            params = []
            if series and series != "(any)":
                where.append("cm.series = ?"); params.append(series)
            if is_proof != "(any)":
                pv = 1 if "Proof" in is_proof else 0
                where.append("ct.is_proof = ?"); params.append(pv)
            if mint_csv.strip():
                mints = [m.strip() for m in mint_csv.split(",") if m.strip()]
                if mints:
                    placeholders = ",".join(["?"]*len(mints))
                    where.append(f"ct.mint_mark IN ({placeholders})"); params.extend(mints)
            if year_min and year_min > 0:
                where.append("ct.year >= ?"); params.append(int(year_min))
            if year_max and year_max > 0:
                where.append("ct.year <= ?"); params.append(int(year_max))
            if year_list.strip():
                where.append("instr(','||?||',', ','||ct.year||',') > 0"); params.append(",".join([y.strip() for y in year_list.split(",") if y.strip()]))
            if variety_like.strip():
                where.append("ct.variety LIKE ?"); params.append(variety_like.strip())

            sql = f"""
                SELECT ct.id, cm.series, ct.year, ct.mint_mark, COALESCE(ct.variety,'') AS variety, ct.is_proof
                FROM coin_type ct JOIN coin_master cm ON cm.id = ct.master_id
                WHERE {' AND '.join(where)}
                ORDER BY cm.series, ct.year, ct.mint_mark, ct.variety
            """
            with get_conn() as cx:
                rows = cx.execute(sql, tuple(params)).fetchall()
            if rows:
                df = pd.DataFrame([dict(r) for r in rows])
                st.dataframe(df, use_container_width=True)
                st.success(f"{len(rows)} matches.")
            else:
                st.info("No matches for that rule.")

        if st.button("Save set (RULES)"):
            if not name.strip():
                st.error("Name is required.")
            else:
                set_id = create_set(name, desc, "RULES")
                add_rule(set_id,
                         series=None if series=="(any)" else series,
                         is_proof=None if is_proof=="(any)" else (1 if "Proof" in is_proof else 0),
                         mint_mark_in=mint_csv.strip() or None,
                         year_min=int(year_min) if year_min>0 else None,
                         year_max=int(year_max) if year_max>0 else None,
                         year_list=",".join([y.strip() for y in year_list.split(",") if y.strip()]) or None,
                         variety_like=variety_like.strip() or None)
                st.success(f"Created rules-based set “{name}”. See progress in My Sets.")

    else:  # MANUAL
        labels, ids = list_coin_types_for_picker()
        st.caption("Pick the exact coin types you want in this set.")
        picks = st.multiselect("Coin Types", labels, default=[])
        req_qty = st.number_input("Required qty for each", min_value=1, step=1, value=1)
        if st.button("Save set (MANUAL)"):
            if not name.strip():
                st.error("Name is required.")
            elif not picks:
                st.error("Pick at least one coin type.")
            else:
                set_id = create_set(name, desc, "MANUAL")
                id_map = {lab: ids[i] for i, lab in enumerate(labels)}
                for lab in picks:
                    add_item(set_id, id_map[lab], int(req_qty))
                st.success(f"Created manual set “{name}”. See progress in My Sets.")

# ---- Manage ----
with tab_manage:
    sets_ = list_sets()
    if not sets_:
        st.info("No Type Sets yet.")
    else:
        by_name = {s["name"]: s for s in sets_}
        nm = st.selectbox("Select a set", list(by_name.keys()))
        s = by_name[nm]

        new_name = st.text_input("Rename", value=s["name"])
        new_desc = st.text_input("Description", value=s.get("description") or "")
        if st.button("Save changes"):
            with get_conn() as cx:
                cx.execute("UPDATE type_set SET name=?, description=? WHERE id=?", (new_name.strip(), new_desc or None, s["id"]))
            st.success("Updated.")

        st.divider()
        if st.button("Delete this set", type="secondary"):
            with get_conn() as cx:
                cx.execute("DELETE FROM type_set WHERE id=?", (s["id"],))
            st.success("Deleted. Refresh the page.")