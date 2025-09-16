# ---- Import Libraries ----
import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import altair as alt

# ---- Page configuration ----
st.set_page_config(
    page_title="Monitoring Produk Lokal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded")

# ---- Load data ----
df = pd.read_excel('Identifikasi-Brand-E-Commerce.xlsx')
gdf = gpd.read_file("idn_adm_bps_20200401_shp/idn_admbnda_adm1_bps_20200401.shp")

# ---- Pre-processing ----
selected_columns = [
    'PRODUCT LINK', 'TITLE', 'PRICE', 'MARKETPLACE', 'BRAND',
    'ASAL BRAND', 'Kategori', 'Lokasi'
]

df = df[selected_columns]

df = df.dropna()

df.drop_duplicates()

df = df[df['ASAL BRAND'] != '-']

# ---- Plots ----

def donut_chart(df):
    # Hitung jumlah produk lokal vs impor
    lokal = df[df["ASAL BRAND"] == "ID"].shape[0]
    impor = df[df["ASAL BRAND"] != "ID"].shape[0]

    counts = pd.DataFrame({
        "Produk": ["Lokal", "Impor"],
        "Jumlah": [lokal, impor]
    })
    counts["Persentase"] = counts["Jumlah"] / counts["Jumlah"].sum()

    # Warna custom
    custom_colors = alt.Scale(
        domain=["Lokal", "Impor"],
        range=["#1f77b4", "#ff4b4b"]
    )

    # Selection interaktif (default pilih "Lokal")
    selection = alt.selection_point(
        fields=["Produk"],
        value="Lokal",
        empty="none"
    )

    base = alt.Chart(counts).encode(
        theta=alt.Theta("Jumlah:Q", stack=True),
        color=alt.Color("Produk:N", scale=custom_colors),
        opacity=alt.condition(selection, alt.value(1), alt.value(0.5)),
        tooltip=[
            alt.Tooltip("Produk:N"),
            alt.Tooltip("Jumlah:Q"),
            alt.Tooltip("Persentase:Q", format=".1%")
        ]
    ).properties(height=280)

    pie = base.mark_arc(innerRadius=72, outerRadius=130).add_selection(selection)

    # Label tengah
    text = alt.Chart(counts).mark_text(
        font="Lato",
        fontSize=30,
        fontWeight=700,
        fontStyle="italic"
    ).encode(
        text=alt.condition(
            selection,
            alt.Text("Persentase:Q", format=".1%"),
            alt.value("")
        ),
        color=alt.condition(
            selection,
            alt.Color("Produk:N", scale=custom_colors),
            alt.value("")
        )
    ).transform_filter(selection)

    chart = pie + text
    st.altair_chart(chart, use_container_width=True)

    return counts

def bar_chart(df):
    df = df[(df['Kategori'].apply(lambda x: isinstance(x, str))) & (df['ASAL BRAND'] == 'ID')]
    kategori_counts = (
        df['Kategori']
        .value_counts()
        .reset_index(name='Jumlah Produk')
        .rename(columns={'index': 'Kategori'})
    )
    
    st.dataframe(
        data=kategori_counts,
        hide_index=True,
        column_config={
            "Kategori": st.column_config.TextColumn("Kategori"),
            "Jumlah Produk": st.column_config.ProgressColumn(
                "Jumlah Produk",
                format="%d",
                min_value=0,
                max_value=int(kategori_counts["Jumlah Produk"].max())
                if not kategori_counts.empty else 0,
            ),
        },
        use_container_width=True
    )

def map_choropleth(df):
    # Hitung jumlah penjual produk lokal per provinsi
    count = (
        df[df["ASAL BRAND"] == "ID"]
        .groupby("Lokasi").size()
        .reset_index(name="count")
    )

    # Gabungkan dengan geojson
    merged = gdf.merge(count, left_on="ADM1_EN", right_on="Lokasi", how="left")
    merged["count"] = merged["count"].fillna(0)
    merged["Lokasi"] = merged["Lokasi"].fillna(merged["ADM1_EN"])

    # Buat choropleth
    fig = px.choropleth(
        merged,
        geojson=merged.__geo_interface__,
        locations=merged.index,  # gunakan index sebagai id unik
        color="count",
        color_continuous_scale=selected_color_theme,
        hover_name="Lokasi",
    )

    fig.update_traces(
        hovertemplate="<b>%{hovertext}</b><br>Jumlah Penjual: %{z}<extra></extra>"
    )

    # Fokus ke Indonesia
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=500)

    # Tampilkan chart dengan interaksi klik
    event = st.plotly_chart(
        fig,
        on_select="rerun",                 # rerun saat ada seleksi
        selection_mode=["points", "box"]   # bisa klik tunggal atau kotak
    )

    # Ambil provinsi yang diklik
    points = event["selection"].get("points", [])
    if points:
        provinsi_idx = points[0].get("location")
        provinsi = merged.loc[provinsi_idx, "Lokasi"]
    else:
        provinsi = None

    # Jika ada provinsi dipilih, tampilkan kategori produk
    if provinsi:
        st.subheader(f"📦 Kategori Produk di {provinsi}")
        kategori_count = (
            df[(df["ASAL BRAND"] == "ID") & (df["Lokasi"] == provinsi)]
            .groupby("Kategori").size().reset_index(name="Jumlah Produk")
            .sort_values("Jumlah Produk", ascending=False)
        )

        st.dataframe(kategori_count, hide_index=True, use_container_width=True)

def grouped_bar_chart(df):
    # Buat kolom baru asal produk
    df_grouped_bar = df.copy()
    df_grouped_bar['Produk'] = df_grouped_bar['ASAL BRAND'].apply(
        lambda x: 'Lokal' if x == 'ID' else 'Impor'
    )

    # Filter hanya produk dengan label jelas
    df_grouped_bar = df_grouped_bar[df_grouped_bar['Produk'].isin(['Lokal', 'Impor'])]

    # Group by kategori & produk
    grouped_price = (
        df_grouped_bar.groupby(['Kategori', 'Produk'])['PRICE']
        .mean()
        .reset_index()
        .rename(columns={'PRICE': 'Mean Price'})
    )

    # Chart bar rata-rata harga (grouped bar)
    bar_chart = (
        alt.Chart(grouped_price)
        .mark_bar()
        .encode(
            x=alt.X("Kategori:N", title="Kategori", axis=alt.Axis(labelAngle=-45)),
            y=alt.Y("Mean Price:Q", title="Rata-rata Harga"),
            color=alt.Color("Produk:N",
                            scale=alt.Scale(domain=["Lokal", "Impor"],
                                            range=["#1f77b4", "#ff4b4b"]),
                            legend=alt.Legend(title="Produk")),
            xOffset="Produk:N",  # supaya grouped, bukan stacked
            tooltip=[
                alt.Tooltip("Kategori:N", title="Kategori"),
                alt.Tooltip("Produk:N", title="Produk"),
                alt.Tooltip("Mean Price:Q", title='Harga Rata-rata', format=',.2f')
            ]
        )
        .properties(
            width=700,
            height=500
        )
    )

    st.altair_chart(bar_chart, use_container_width=True)

def boxplot(df, kategori):
    # Buat kolom baru asal produk
    df_box = df.copy()
    df_box['Jenis Produk'] = df_box['ASAL BRAND'].apply(lambda x: 'Lokal' if x == 'ID' else 'Impor')

    # Filter hanya produk dengan label jelas
    df_box = df_box[df_box['Jenis Produk'].isin(['Lokal', 'Impor'])]

    # Filter kategori (kecuali kalau pilih "Semua Kategori")
    if kategori != "Semua Kategori":
        df_box = df_box[df_box["Kategori"] == kategori]

    q95 = df_box["PRICE"].quantile(0.95)
        
    # Buat boxplot
    fig = px.box(
        df_box,
        x='Jenis Produk',
        y='PRICE',
        color='Jenis Produk',
        color_discrete_map={'Lokal': '#1f77b4', 'Impor': '#ff4b4b'}
    )

    fig.update_layout(
        xaxis_title='Jenis Produk',
        yaxis_title='Harga Produk',
        yaxis_range = [0, q95 * 1.1],
        width=800,
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

# ---- Sidebar ----
with st.sidebar:
    st.title('🛍️ Dashboard Monitoring Produk Lokal di Marketplace')
    st.markdown("""
    Visualisasi interaktif produk lokal di marketplace Indonesia. 
    Dashboard ini dirancang untuk memantau tren, distribusi, dan perbandingan produk lokal dengan produk impor sebagai dasar pertimbangan kebijakan strategis.
    """)

    color_theme_list = ['blues', 'cividis', 'greens', 'inferno', 'magma', 'plasma', 'reds', 'rainbow', 'turbo', 'viridis']
    selected_color_theme = st.selectbox('Pilih tema warna', color_theme_list)

# ---- Main Content ----
st.markdown(
    """
    <style>
    /* Atur font dan padding tab */
    button[data-baseweb="tab"] p {
        font-size: 18px !important;
        padding: 10px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

tab = st.tabs(["Dominasi Produk", "Sebaran Lokasi", "Analisis Harga"])

# TAB 1: Dominasi Produk
with tab[0]:
    st.subheader("📦 Dominasi Produk Lokal vs Impor")
    st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

    col = st.columns((1.2, 2), gap='medium')
    with col[0]:
        counts = donut_chart(df)
    with col[1]:
        lokal_pct = counts[counts["Produk"] == "Lokal"]["Persentase"].values[0] * 100
        impor_pct = counts[counts["Produk"] == "Impor"]["Persentase"].values[0] * 100

        st.markdown(
            f"""
            Produk lokal mencakup **{lokal_pct:.1f}%** sedangkan produk impor mencakup **{impor_pct:.1f}%** dari total penawaran di e-commerce. 
            Perbandingan ini memberikan gambaran mengenai komposisi produk yang tersedia di pasar digital, serta menunjukkan bagaimana kedua jenis produk hadir dan bersaing di platform online.
            
            Informasi ini bermanfaat untuk memahami kecenderungan penawaran produk di e-commerce, baik dalam melihat kekuatan produk dalam negeri maupun posisi produk impor di tengah persaingan pasar.
            """
        )
    
    st.subheader("🔍 Analisis Produk Lokal Berdasarkan Marketplace")

    col = st.columns((1.5, 2), gap='medium')
    with col[0]:
        # Filter interaktif
        marketplace_list = ['Semua Marketplace', 'Blibli', 'Bukalapak', 'OLX']
        selected_marketplace = st.selectbox('Pilih marketplace', marketplace_list)

        # Filter dataset
        if selected_marketplace == "Semua Marketplace":
            df_filtered = df
        else:
            df_filtered = df[(df["MARKETPLACE"] == selected_marketplace)]

        jumlah_lokal = df_filtered[df_filtered['ASAL BRAND'] == 'ID'].shape[0]
        total_produk = df_filtered.shape[0]

        persentase_lokal = (jumlah_lokal / total_produk * 100) if total_produk > 0 else 0

        # Metric ringkasan
        st.markdown(
            f"""
            <div style="font-size:18px; font-weight:400; color:black;">
                Produk Lokal di <strong>{selected_marketplace}</strong>
            </div>
            <div style="font-size:36px; font-weight:500;">
                {persentase_lokal:.1f}%
                <span style="font-size:18px; color:black;"> ({jumlah_lokal:,} dari {total_produk:,} produk)</span>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown(
            """
            Bagian ini menampilkan jumlah produk lokal yang tersedia di setiap marketplace. 
            Informasi ini membantu untuk memahami seberapa besar kontribusi produk lokal dalam platform yang dipilih, sekaligus memperlihatkan kategori mana yang lebih dominan. 
            Dengan demikian, tren distribusi produk lokal dapat dipantau secara lebih terarah.
            """
        )

    with col[1]:
        bar_chart(df_filtered)

# TAB 2: Sebaran Lokasi
with tab[1]:
    st.subheader("🗺️ Sebaran Lokasi Penjual Produk Lokal")
    st.markdown("Peta ini menunjukkan konsentrasi penjual produk lokal di setiap provinsi.")
    map_choropleth(df)

# TAB 3: Analisis Harga
with tab[2]:
    st.subheader("💰 Rata-rata Harga Produk Lokal vs Impor Setiap Kategori")
    st.markdown("<div style='margin-bottom:15px;'></div>", unsafe_allow_html=True)

    grouped_bar_chart(df)

    st.subheader("💳 Distribusi Harga Produk Lokal vs Impor")
    col = st.columns((1.5, 2), gap='medium')

    with col[0]:
        kategori_list = [
            'Semua Kategori',
            'Elektronik & Gadget',
            'Fashion & Aksesoris',
            'Hobi, Seni, & Olahraga',
            'Ibu, Bayi & Anak',
            'Lain-Lain',
            'Makanan & Minuman',
            'Otomotif & Mesin',
            'Perawatan Diri & Kesehatan',
            'Rumah Tangga & Furniture'
        ]
        selected_kategori = st.selectbox('Pilih Kategori', kategori_list)

        # Hitung rata-rata harga lokal vs impor
        mean_lokal = df[df["ASAL BRAND"] == "ID"]["PRICE"].mean()
        mean_impor = df[df["ASAL BRAND"] != "ID"]["PRICE"].mean()

        if mean_lokal < mean_impor:
            insight = (
                "Produk impor umumnya berada pada kisaran harga yang lebih tinggi, sementara produk lokal cenderung lebih terjangkau."
            )
        elif mean_lokal > mean_impor:
            insight = (
                "Produk lokal justru memiliki rata-rata harga lebih tinggi dibandingkan produk impor, menunjukkan adanya segmen premium pada produk dalam negeri."
            )
        else:
            insight = (
                "Harga produk lokal dan impor relatif seimbang, menunjukkan persaingan yang cukup setara di pasar e-commerce."
            )

        st.markdown(
            f"""
            Distribusi harga produk lokal dan impor menunjukkan adanya perbedaan pola di pasar. 
            {insight}

            Informasi ini memberi gambaran bagaimana kedua jenis produk menempati segmen harga dan bagaimana konsumen dapat mempertimbangkan pilihan sesuai kebutuhan.
            """
        )

    with col[1]:
        if selected_kategori != "Semua Kategori":
            st.markdown(
                f"<h3 style='text-align: center; font-size: 16px; margin-bottom: -32px; font-weight: 600;'>Distribusi Harga Produk Lokal vs Impor di Kategori {selected_kategori}</h3>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<h3 style='text-align: center; font-size: 18px; margin-bottom: -32px; font-weight: 600;'>Distribusi Harga Produk Lokal dan Impor di Semua Kategori</h3>",
                unsafe_allow_html=True
            )
        
        boxplot(df, selected_kategori)
