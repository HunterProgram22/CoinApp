# pages/10_Type_Sets.py
import streamlit as st
import pandas as pd
from db import get_conn

st.header("📚 Type Sets")

# ------------------------ Helpers ------------------------
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

def get_progress(set_id: int):
    with get_conn() as cx:
        rows = cx.execute("""
            SELECT * FROM v_type_set_progress
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

def export_missing_csv(set_id: int):
    rows = get_progress(set_id)
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    missing = df[df["have_qty"] < df["required_qty"]].copy()
    cols = ["series","year","mint_mark","variety","is_proof","required_qty","have_qty","coin_type_id"]
    missing = missing[cols]
    return missing

# ------------------------ UI ------------------------
tab_browse, tab_new, tab_manage = st.tabs(["My Sets", "New Set", "Manage"])

# ---- My Sets (progress) ----
with tab_browse:
    sets_ = list_sets()
    if not sets_:
        st.info("No Type Sets yet. Create one in the 'New Set' tab.")
    else:
        name_to_id = {f"{s['name']} [{s['mode']}]" : s["id"] for s in sets_}
        sel_name = st.selectbox("Select a set", list(name_to_id.keys()))
        set_id = name_to_id[sel_name]
        rows = get_progress(set_id)
        total = len(rows)
        done = sum(1 for r in rows if r["is_complete"] == 1)
        st.metric("Progress", f"{done}/{total} complete")

        if rows:
            df = pd.DataFrame(rows)
            df = df.rename(columns={
                "series":"Series","year":"Year","mint_mark":"Mint Mark","variety":"Variety",
                "is_proof":"Proof","required_qty":"Required","have_qty":"On Hand","is_complete":"Done"
            })
            df["Done"] = df["Done"].map({0:"❌",1:"✅"})
            st.dataframe(df[["Series","Year","Mint Mark","Variety","Proof","Required","On Hand","Done"]],
                         use_container_width=True)

            if st.button("Export missing as CSV"):
                missing = export_missing_csv(set_id)
                if missing is None or missing.empty:
                    st.info("Nothing missing—nice!")
                else:
                    fn = f"type_set_missing_{set_id}.csv"
                    missing.to_csv(f"/mnt/data/{fn}", index=False)
                    st.success(f"Saved: {fn}")
                    st.markdown(f"[Download {fn}](sandbox:/mnt/data/{fn})")

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