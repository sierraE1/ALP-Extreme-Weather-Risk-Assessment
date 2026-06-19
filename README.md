# Flood Map Dashboard

This folder contains the flood map website.

## Work log

Here is a record of what I did to process the data and make the diagrams.

1. I opened the flood data and cleaned it in Python.
2. I fixed the date fields, area values, and column names so the data was easier to use.
3. I kept the data in a useful date range for the analysis.
4. I created year, month, and duration columns so the records could be grouped and compared.
5. I used Python plotting tools to draw the charts.
6. I made bar charts for yearly and monthly patterns, scatter plots for area and duration, and box plots for severity comparisons.
7. I used these Python packages for the charts and data work: `pandas`, `numpy`, `matplotlib`, `seaborn`, `pyarrow`, `scikit-learn`, and `shapely`.
8. I saved the finished charts into the output folder.

## Result

The final output is a set of flood analysis charts that show trends, seasonality, causes, and comparisons between the datasets.

## Setup guide

### What you need

- VS Code
- Node.js installed --> https://nodejs.org/en/download




## Backend folder

This is the part that makes the data visualizations.

### Step 1: Open the backend folder

Open the `Data_Cleaning` folder in VS Code.

### Step 2: Open the terminal

In VS Code, open the terminal from the top menu.

### Step 3: Run the Python script

Type this command and press Enter:

```bash
python Processing.py
```

### Step 4: Wait for the charts

The script will clean the data and create the chart images in the output folder.





### Frontend folder

This is the part that makes runs the GitHub pages map visualization.

### Step 1: Open the folder

Open the `Map_Visualization/Frontend` folder in VS Code.

### Step 2: Open the terminal

In VS Code, open the terminal from the top menu.

### Step 3: Install the website files

Type this command and press Enter:

```bash
npm install
```

### Step 4: Start the website

Type this command and press Enter:

```bash
npm run dev
```

### Step 5: Open the link

The terminal will show a web address, usually `http://localhost:5173`.
Open that address in your browser.

## If something goes wrong

- Make sure Node.js is installed.
- Make sure you are in the `Frontend` folder before running the commands.
- If the site does not open, run `npm install` again and then try `npm run dev` again.

## Helpful note

The map app needs the flood data file to be ready first. If the map is empty, the data may still need to be prepared.