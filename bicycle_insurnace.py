import os
import pandas as pd
import ipdb
import numpy as np
import collections
from pprint import pprint as pp
from tqdm import tqdm

class bicycle_insurance_EDA():
    def __init__(self, dataset_path,mode='EXP'):
        '''
        mode: EXP or DEV, DEV will load few csv file to save developing time
        dataset_path: path for dataset
        months: months folder name in dataset
        regioins_dist: files name in each month folder
        all_df: concatinate all csv file into a DataFrame
        area_df: build area using LSOA name, and compuate it mean coordinate
        ni_area_df: northern ireland area and its coordinate
        summary: bicycle theft crime summary in each area for each month
        price_df: bicycle insurace price in each area for each month
        '''
        self.mode = mode
        self.dataset_path=dataset_path
        self.months = os.listdir(dataset_path)
        self.months.sort()
        self.regions_dict = {}
        self.missing_regions = {}
        self.all_regions = set()
        self.regions_df_dict = {}
        self.all_df = pd.DataFrame()
        self.area_df = None
        self.ni_area_df = None
        self.summary = None
        self.price_df = None

    def northern_ireland_area(self):
        '''
        area: https://www.police.uk/northern-ireland/
        coordinate: google map
        '''
        ni_area = {
                'Antrim':'54.719610,-6.207239',
                'Armagh':'54.350298,-6.652791',
                'Ballymena':'54.865297,-6.280219',
                'Castlereagh':'54.575749,-5.888258',
                'Coleraine':'55.132580,-6.664610',
                'Crossmaglen':'54.077413,-6.608756',
                'Downpatrick':'54.328760,-5.715700',
                'Dungannon':'54.508275,-6.766969',
                'Enniskillen':'54.343826,-7.631546',
                'Larne':'54.857801,-5.823623',
                'Limavady':'55.045459,-6.933668',
                'Lisburn':'54.516257,-6.057991',
                'Lisburn Road':'54.577390,-5.952863',
                'Lisnaskea':'54.252895,-7.442876',
                'Lurgan':'54.463672,-6.334950',
                'Magherafelt':'54.755361,-6.608004',
                'Newry':'54.175100,-6.340185',
                'Newtownabbey':'54.669108,-5.902554',
                'Newtownards':'54.591377,-5.693180',
                'Newtownhamilton':'54.193605,-6.576330',
                'Omagh':'54.597696,-7.309958',
                'Strabane':'54.827382,-7.463297',
                'Strand Road':'55.006160,-7.320743',
                'Strandtown':'54.600942,-5.882469',
                'Tennent Street':'54.607721,-5.954411',
                'Woodbourne':'54.568574,-6.013230',
        }
        df_dict = {'file':['northern-ireland-street.csv' for i in range(len(ni_area))],
                'area':[a for a in ni_area.keys()],
                'area_coor':[c for c in ni_area.values()]}
        self.ni_area_df = pd.DataFrame.from_dict(df_dict)

    def check_missing_regions(self):
        '''
        check missing regions in each month
        '''
        for month in self.months:
            folder_path = self.dataset_path+month
            if os.path.isdir(folder_path):
                regions = os.listdir(folder_path)
                regions = [r.replace(month+'-', '') for r in regions]
                self.regions_dict[month] = regions
                self.all_regions |= set(regions)

        for month, regions in self.regions_dict.items():
            missing_regions = self.all_regions - set(regions)
            if len(missing_regions) > 0:
                self.missing_regions[month]= list(missing_regions)
                print(f'missing files: {month}: {missing_regions}')

    def load_csv(self):
        # combine df based on region
        # filter crime type for saving computing time
        count=0
        for month, regions in tqdm(self.regions_dict.items()):
            for r in regions:
                df = pd.read_csv(self.dataset_path+month+'/'+month+'-'+r)
                df = df[df['Crime type' ].str.contains("Bicycle theft")]
                df.insert(loc=0, column='file', value=r)
                self.all_df = pd.concat([self.all_df,df]) if len(self.all_df>0) else df

            count+=1
            if(self.mode=='DEV' and count==2):
                break

        self.all_df.reset_index(drop=True, inplace=True)

    def add_area(self):
        '''
        generate area column by removeing the last code in LSOA name
        '''
        self.all_df['area'] = self.all_df['LSOA name'].map(lambda x: " ".join(s for s in (str(x).split()[:-1])))

    def group_by_column_count(self, columns):
        '''
        count how many crime based on given columns
        '''
        count_df = self.all_df.groupby(columns).size().reset_index(name='counts').sort_values(by=['counts'])
        c_str = (' '.join(columns)).replace(' ','_')
        count_df.to_csv(f'./stage1.0-group_by_column_count_{c_str}.csv')

    def get_area_coor(self):
        '''
        build area cooridnate by average all bicycle crime in that area.
        this cooridnate is an approximation for recovering missing area (LSOA code)
        '''
        assert 'area' in self.all_df
        self.area_df = self.all_df[['file','area']]
        self.area_df = self.area_df.groupby(['file','area']).size().reset_index(name='counts')
        area_list = self.area_df['area'].values.tolist()
        self.all_df['area_coor'] = ''

        print('building area coorindate, please wati......')
        for area in tqdm(area_list):
            if area != '':
                mean_coor = self.all_df[self.all_df['area']==area][['Latitude','Longitude']].mean(axis=0)
                self.all_df.loc[self.all_df['area']==area,['area_coor']] = [str(mean_coor['Latitude'].item())+','+str(mean_coor['Longitude'].item())] * len(self.all_df[self.all_df['area']==area])

        self.area_df = self.all_df.groupby(['file','area','area_coor']).size().reset_index(name='counts')
        self.area_df = self.area_df[self.area_df['file']!='btp-street.csv']
        self.area_df = self.area_df[self.area_df['area_coor']!='']

        # there some cross force crime like: london city reported by Manchester,
        # remove duplicate, keep only the first area that has largest count
        self.area_df = self.area_df.sort_values(by=['counts'], ascending=False).drop_duplicates(['area'],keep='first').sort_values(by=['file'])
        self.area_df = pd.concat([self.area_df, self.ni_area_df]).reset_index(drop=True).reset_index(drop=True)

        self.summary = self.area_df[['file','area']]
        self.area_df.to_csv('stage1.1-area_coor.csv')

    def recover_area(self):
        '''
        recovering missing area (LSOA code)
        '''
        def find_close_coordinate_area(src, dest):
            areas = []
            for s in src:
                # for de in dest:
                    # de[0]
                    # import ipdb; ipdb.set_trace();
                distances = np.array([(float(s[0])-float(de[0]))**2+(float(s[1])-float(de[1]))**2 for de in dest])
                area = self.area_df.iloc[np.argmin(distances)]['area']
                areas.append(area)
            return areas

        nan_losa = self.check_Nan(['LSOA code'], opt='any')
        nan_losa_with_coordinate = nan_losa[nan_losa[['Latitude','Longitude']].notnull().all(axis=1)]

        src_df = nan_losa_with_coordinate
        src_df['latlng'] = list(zip(nan_losa_with_coordinate['Latitude'], nan_losa_with_coordinate['Longitude']))
        dest_df=self.area_df

        src = src_df['latlng'].values.tolist()
        dest = dest_df['area_coor'].values.tolist()
        dest = [d.split(',') for d in dest]

        areas = find_close_coordinate_area(src, dest)
        nan_losa_with_coordinate['area']=areas

        self.all_df.loc[nan_losa_with_coordinate.index,['area']]=areas

        # check empty area with coor, should be empty
        empty_area = self.all_df[self.all_df['area']=='']
        empty_area_count = empty_area[empty_area[['Latitude','Longitude']].notnull().all(axis=1)]
        print(f'empty area with coor: {empty_area_count}')

    def check_Nan(self, column, opt='any'):
        if opt=='any':
            nan_df = self.all_df[self.all_df[column].isnull().any(axis=1)]
        elif opt=='all':
            nan_df = self.all_df[self.all_df[column].isnull().all(axis=1)]
        return nan_df

    def check_duplicate(self, columns, remove_null=True):
        assert columns!=None
        df_columns = self.all_df[columns]
        duplicate_df = self.all_df[df_columns.duplicated(keep=False)].sort_values(by=['Crime ID'])
        if remove_null: duplicate_df = duplicate_df[duplicate_df["Crime ID"].notnull()]
        return duplicate_df

    def remove_duplicate(self, columns):
        self.all_df = self.all_df.drop_duplicates(columns, keep='first')

    def get_monthly_summary(self):
        '''
        calculate monthly bicycle crime based on each area.
        '''
        for month in tqdm(self.months):
            month_df = self.all_df[self.all_df['Month']==month]
            month_summary_df = month_df.groupby(['Month', 'area']).size().reset_index(name='counts')
            merge = pd.merge(self.summary, month_summary_df, how='left', on='area')

            nan_area = month_df[month_df[['LSOA code', 'Latitude', 'Longitude']].isnull().all(axis=1)]
            nan_area_crime_count_in_file = nan_area.groupby(['file']).size().reset_index(name='crime_count')
            area_count_in_file = self.summary.groupby(['file']).size().reset_index(name='area_count')
            nan_merge = pd.merge(area_count_in_file, nan_area_crime_count_in_file, how='left', on='file').fillna(0)
            nan_merge['avg_crime'] = nan_merge['crime_count'] / nan_merge['area_count']
            merge = pd.merge(merge, nan_merge, on='file', how='outer')

            self.summary[month] = np.nan_to_num(merge['counts'].values.tolist()) + merge['avg_crime'].values.tolist()
        self.summary.to_csv('stage2.0-monthly_summary.csv')

    def fill_missing_data(self):
        '''
        fill missing regions data
        '''
        for month, files in self.missing_regions.items():
            for f in files:
                if f != 'btp-street.csv':
                    self.summary.loc[(self.summary['file']==f), month] = np.nan
                    block_df = self.summary.loc[(self.summary['file']==f),self.months]
                    interpolate_df = block_df.transpose().reset_index(drop=True).interpolate(method='spline',order=1).transpose()
                    self.summary.loc[(self.summary['file']==f),self.months] = interpolate_df.values
        self.summary.to_csv('stage2.1-monthly_summary_fillna.csv')

    def calculate_monthly_price(self):
        '''
        get final monthly bicycle insurace price based on each area bicycle theft count
        the lowest price maintain 1£
        '''
        self.price_df = self.summary.copy()
        pre_crime_count = np.zeros(len(self.price_df))
        pre_price = np.ones(len(self.price_df))

        for month in self.months:
            crime_count = self.summary.loc[:,month].values
            half = (crime_count <= (pre_crime_count/2))

            price_change = crime_count * (1-half) + (-1)*half
            price = pre_price + price_change
            price = (price<1)*1 + (price>=1)*(price)
            self.price_df.loc[:,month] = price

            pre_price = price
            pre_crime_count = crime_count

        self.price_df.to_csv('stage2.2-monthly_price.csv')

        return

def build_df(bicycle_eda):
    bicycle_eda.check_missing_regions()
    import ipdb; ipdb.set_trace();

    if not os.path.isfile('./stage0-all_df.csv'):
        print('Building DataFrame, please wait.....')
        bicycle_eda.load_csv()
        bicycle_eda.northern_ireland_area()
        bicycle_eda.add_area()
        bicycle_eda.all_df.to_csv('./stage0-all_df.csv')
    else:
        bicycle_eda.all_df = pd.read_csv('./stage0-all_df.csv')

def EDA(bicycle_eda):
    # check counts on different columns, to decide the price based on which level of area
    bicycle_eda.group_by_column_count(['file'])
    bicycle_eda.group_by_column_count(['area'])
    bicycle_eda.group_by_column_count(['LSOA code', 'LSOA name'])

    # build area coor by coor average
    bicycle_eda.get_area_coor()

    # get all losa is nan,
    nan_losa = bicycle_eda.check_Nan(['LSOA code'], opt='any')
    nan_losa.to_csv('stage1.2-nan_losa.csv')

    # get all losa is nan but has coordinate,
    nan_losa_with_coordinate = nan_losa[nan_losa[['Latitude','Longitude']].notnull().all(axis=1)]
    nan_losa_with_coordinate.to_csv('stage1.2-nan_losa_with_coordinate.csv')

    # we try to recover area using area coordinate
    bicycle_eda.recover_area()

    # Crime ID is nan, only happen in public transport police,
    # and crime can seperate based on area or coor
    nan_crimeid = bicycle_eda.check_Nan(['Crime ID'], opt='any')
    nan_crimeid.to_csv('stage1.3-nan_crimeid.csv')

    # and all case can find area
    nan_crimeid_losa =bicycle_eda.check_Nan(['LSOA code','Crime ID'], opt='all')
    nan_crimeid_losa.to_csv('stage1.3-nan_crimeid_losa.csv')

    # and all case have coordinate
    nan_crimeid_losa_area =bicycle_eda.check_Nan(['LSOA code','Crime ID', 'area'], opt='all')
    nan_crimeid_losa_area.to_csv('stage1.3-nan_crimeid_losa_area.csv')

    # duplicate ID
    # some duplicate ID have different Month, Location, coordinate.
    # They are potentially different case but have same ID
    dup_crimeid = bicycle_eda.check_duplicate(['Crime ID'], True)
    dup_crimeid.to_csv('stage1.4-dup_crimeid.csv')

    # duplicate based on multiple columns
    # These are more likely duplicate case
    dup_multi_columns = bicycle_eda.check_duplicate(['Crime ID'
                                    ,'Reported by'
                                    ,'Falls within'
                                    ,'Longitude'
                                    ,'Latitude'
                                    ,'Location'
                                    ,'LSOA code'
                                    ,'LSOA name'
                                    ,'Crime type'
                                    ])
    dup_multi_columns.to_csv('stage1.4-dup_multi_columns.csv')

    # remove duplicate
    bicycle_eda.remove_duplicate(['Crime ID'
                                    ,'Reported by'
                                    ,'Falls within'
                                    ,'Longitude'
                                    ,'Latitude'
                                    ,'Location'
                                    ,'LSOA code'
                                    ,'LSOA name'
                                    ,'Crime type'
                                    ])

    # check again
    check_dup_multi_columns = bicycle_eda.check_duplicate(['Crime ID'
                                    ,'Reported by'
                                    ,'Falls within'
                                    ,'Longitude'
                                    ,'Latitude'
                                    ,'Location'
                                    ,'LSOA code'
                                    ,'LSOA name'
                                    ,'Crime type'
                                    ])
    check_dup_multi_columns.to_csv('stage1.4-remove_dup_multi_columns.csv')

    # get all losa and coordinate is nan
    # will distribute these case equally to areas within this region
    nan_losa_coordinate = bicycle_eda.check_Nan(['LSOA code', 'Latitude', 'Longitude'], opt='all')
    nan_losa_coordinate.to_csv('stage1.5-nan_losa_coordinate.csv')

def build_price(bicycle_eda):
    bicycle_eda.get_monthly_summary()

    bicycle_eda.fill_missing_data()

    bicycle_eda.calculate_monthly_price()

if __name__ == '__main__':
    print( '%s: calling main function ... ' % os.path.basename(__file__))

    bicycle_eda = bicycle_insurance_EDA('./bicycle/', 'EXP')

    build_df(bicycle_eda)
    EDA(bicycle_eda)
    build_price(bicycle_eda)

    print('\nsucess!')

