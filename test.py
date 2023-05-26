import pandas as pd
import matplotlib.pyplot as plt

url = 'https://data.cdc.gov/api/views/w9j2-ggv5/rows.csv?accessType=DOWNLOAD'

df = pd.read_csv(url)
us_data = df[df['Jurisdiction'] == 'United States']
plt.plot(us_data['Year'], us_data['Average Life Expectancy (Years)'])
plt.title('Life Expectancy in the United States')
plt.xlabel('Year')
plt.ylabel('Life Expectancy (Years)')
plt.show()