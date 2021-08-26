import altair as alt
import math
import pandas as pd
import pycountry
from vega_datasets import data

class Sheet:

    def __init__(self, file_location, sheet_name, location_type, skip_rows = [], skip_columns = []):
        self.df = self.get_df(file_location, sheet_name, location_type, skip_rows, skip_columns)
        self.sheet_name = sheet_name
        self.location_type = location_type

    def get_df(self, file_location, sheet_name, location_type, skip_rows, skip_columns):
        df = pd.read_excel(file_location, sheet_name=sheet_name, index_col=None, header=None,
                           skiprows=skip_rows)
        df = df.transpose().drop(skip_columns)
        df = self.fix_header(df)
        df = df.melt(id_vars=location_type, value_name='Budget')
        df = df.rename(columns={location_type: 'Year', 0: location_type})
        df = self.fix_budget(df, location_type)
        df = self.fix_year(df)

        return df

    def fix_header(self, df):
        new_header = df.iloc[0]  # grab the first row for the header
        df = df[1:]  # take the data less the header row
        df.columns = new_header
        return df

    def fix_budget(self, df, location_type):
        df = df.dropna()
        df = self.remove_dead_countries(df, location_type)
        df["Budget"] = df["Budget"].apply(lambda country: self.clean_budget(country)).astype('float64')
        return df

    def remove_dead_countries(self, df, location_type):
        living_countries = df.loc[(df["Year"] == 2020) & (df["Budget"] != "xxx")][location_type].tolist()
        df = df.loc[df[location_type].isin(living_countries)]
        return df

    def clean_budget(self, item):
        try:
            x = float(item)
        except ValueError:
            return None
        if math.isnan(x):
            return None
        return x

    def fix_year(self, df):
        df = df.loc[df["Year"] != "2020 Current"]
        df["Year"] = pd.to_numeric(df["Year"], downcast="integer")
        return df


class Sipri:

    sipri_to_ISO_country_map = {
        "Cape Verde": "Cabo Verde",
        "Congo, Republic of": "Congo",
        "Congo, Dem. Rep.": "Congo, The Democratic Republic of the",
        "Côte d’Ivoire": "Côte d'Ivoire",
        "Trinidad & Tobago": "Trinidad and Tobago",
        "USA": "United States",
        "Korea, South": "Korea, Republic of",
        "Korea, North": "Korea, Democratic People's Republic of",
        "Brunei": "Brunei Darussalam",
        "Bosnia-Herzegovina": "Bosnia and Herzegovina",
        "Russia": "Russian Federation",
        "UK": "United Kingdom",
        "Iran": "Iran, Islamic Republic of",
        "Laos": "Lao People's Democratic Republic",
        "Syria": "Syrian Arab Republic",
        "UAE": "United Arab Emirates"
    }

    def __init__(self, file_location):
        self.constant_USD = self.__read_constant_USD(file_location)
        self.regional_totals = self.__read_regional_totals(file_location)

    def __read_constant_USD(self, file_location):
        skip_rows = list(range(0, 5)) + list(range(198, 205))
        skip_columns = [1, 2]
        return Sheet(file_location, 'Constant (2019) USD', 'Country', skip_rows, skip_columns)

    def __read_regional_totals(self, file_location):
        skip_rows = list(range(0, 14)) + list(range(37, 45))
        skip_columns = [34, 35]
        return Sheet(file_location, 'Regional totals', 'Region', skip_rows, skip_columns)

    def budget_line_chart(self, country_names, tick_year_list, last_year=2021, label_list=[]):
        selected_df = self.__select_df(self.constant_USD, country_names, tick_year_list, last_year)
        if label_list:
            selected_df.insert(3, "Labels", label_list, True)

        base = alt.Chart(selected_df).encode(
            alt.X('Year:O', axis=alt.Axis(values=tick_year_list + [last_year])),
            alt.Y('Budget:Q'),
        ).properties(
            width=500,
            height=500
        )
        lines = base.mark_line().encode(
            alt.Color('Country:N')
        )
        points = lines.mark_circle()
        chart = lines + points

        if label_list:
            labels = base.mark_text(
                align='left',
                baseline='middle',
                dx=3,
                color='black'
            ).encode(
                text='Labels'
            )

            chart = chart + labels

        return chart

    def __select_df(self, sheet, country_names, tick_year_list, last_year=2021):
        full_year_list = list(range(tick_year_list[0], last_year))
        return sheet.df.loc[sheet.df['Year'].isin(full_year_list) & sheet.df[sheet.location_type].isin(country_names)]

    def spending_bar_chart(self, country_names, tick_year_list, last_year=2021):
        selected_df = self.__select_df(self.constant_USD, country_names, tick_year_list, last_year)

        chart = alt.Chart(selected_df).mark_bar().encode(
            alt.X('Country:N'),
            alt.Y('sum(Budget):Q')
        ).properties(
            width=250,
            height=500
        )

        return chart

    def regional_budget_line_chart(self, region_names, tick_year_list):
        selected_df = self.__merge_USA_into_regional(region_names, tick_year_list)

        chart = alt.Chart(selected_df).mark_line().encode(
            alt.X('Year:O', axis=alt.Axis(values=tick_year_list + [2020])),
            alt.Y('Budget:Q'),
            alt.Color('Region:N')
        ).properties(
            width=500,
            height=500
        )

        return chart

    def regional_spending_bar_chart(self, region_names, tick_year_list):
        selected_df = self.__merge_USA_into_regional(region_names, tick_year_list)

        chart = alt.Chart(selected_df).mark_bar().encode(
            alt.X('Region:N'),
            alt.Y('sum(Budget):Q')
        ).properties(
            width=250,
            height=500
        )

        return chart

    def __merge_USA_into_regional(self, region_names, tick_year_list):
        region_df = self.__select_df(self.regional_totals, region_names, tick_year_list)
        usa_df = self.__select_df(self.constant_USD, ["USA"], tick_year_list)
        usa_df = self.__transform_country_to_regional(usa_df)

        if 'Americas' in region_names:
            region_df = self.__subtract_usa_from_americas(region_df, usa_df)

        selected_df = pd.concat([region_df, usa_df], ignore_index=True)
        return selected_df

    def __transform_country_to_regional(self, df):
        df["Budget"] = df["Budget"].map(lambda item : item / 1000)
        return df.rename(columns={'Country': 'Region'})

    def __subtract_usa_from_americas(self, region_df, usa_df):
        americas_df = region_df.loc[region_df['Region'] == 'Americas', ["Year", 'Budget']].set_index('Year') - usa_df[
            ['Year', 'Budget']].set_index('Year')
        americas_df = americas_df.reset_index()
        americas_df['Region'] = pd.Series(['Americas minus US' for x in range(len(americas_df.index))])

        region_df = region_df.drop(region_df.loc[region_df['Region'] == 'Americas'].index)
        return pd.concat([region_df, americas_df])

    def budget_under_price(self, price, year=2019):
        countries = alt.topo_feature(data.world_110m.url, 'countries')

        df = self.constant_USD.df
        budgets = df.loc[df['Year'] == year]
        budgets = budgets.dropna()
        budgets['id'] = budgets.apply(lambda country: self.__get_country_id(country["Country"]), axis=1).astype('int64')
        budgets['bools'] = budgets.apply(lambda country: country["Budget"] < price, axis=1).astype('bool')

        chart = alt.Chart(countries).mark_geoshape(
            stroke='black'
        ).encode(
            color=alt.Color('bools:O', scale=alt.Scale(domain=[True, False, None], scheme='category20'))
        ).transform_lookup(
            lookup='id',
            from_=alt.LookupData(budgets, key='id', fields=['bools'])
        ).project(
            type='equirectangular'
        ).properties(
            width=700,
            height=600,
            title='Countries with Budget under Gerald Ford class Aircraft Carrier'
        )

        return chart + chart

    def __get_country_id(self, country_name):
        if country_name == "Kosovo":
            return 0
        iso = pycountry.countries.get(name=self.__map_country_name(country_name))
        if not iso:
            iso = pycountry.countries.get(common_name=self.__map_country_name(country_name))
        return iso.numeric

    def __map_country_name(self, country_name):
        try:
            mapped_name = self.sipri_to_ISO_country_map[country_name]
        except KeyError:
            mapped_name = country_name

        return mapped_name.replace("Rep.", "Republic")

    def budget_histogram(self, year, removed_countries=[]):
        df = self.constant_USD.df
        budgets = df.loc[(df['Year'] == year) & (df["Country"].isin(removed_countries) == False)]
        budgets = budgets.dropna()

        chart = alt.Chart(budgets).mark_bar().encode(
            alt.X("Budget:Q", bin=alt.Bin(maxbins=20)),
            y='count()',
        ).properties(
            width=200,
            height=600
        )

        return chart

    def budget_histogram_by_scale(self, year, scale):
        df = self.constant_USD.df
        budgets = df.loc[(df['Year'] == year) & (df["Budget"] > scale) & (df["Budget"] < scale * 10)]
        budgets = budgets.dropna()


        chart = alt.Chart(budgets).mark_bar().encode(
            alt.X("Budget:Q", bin=alt.Bin(step=scale, extent=[scale, scale*10])),
            alt.Y('count()', scale=alt.Scale(domain=(0, 20)))
        ).properties(
            width=200,
            height=200
        )

        return chart