import bml.files as bfiles
import os
import glb
import pandas as pd

PALETTE = ['#2a78d6',
           '#eb6834',
           '#1baf7a',
           '#eda100',
           '#e87ba4',
           '#008300',
           '#4a3aa7',
           '#e34948']
MARKERS = ['o', 's', '^', 'D', 'v', 'P', 'X', '*']
NEUTRAL = '#8a8a85'
INK = '#0b0b0b'
INK_SECONDARY = '#52514e'
GRID = '#e3e3e0'

ROLE_COLOURS = {
    'phenotype':   PALETTE[0],
    'batch':       PALETTE[1],
    'shared':      PALETTE[6],
    'interaction': PALETTE[6],
    'residual':    NEUTRAL,
    'unexplained': NEUTRAL,
    'uncorrected': NEUTRAL,
}

def group_colours(n):
    return [PALETTE[i % len(PALETTE)] if i < len(PALETTE) else NEUTRAL for i in range(n)]

def group_markers(n):
    return [MARKERS[i % len(MARKERS)] for i in range(n)]

def style_axes(ax, title=None, xlabel=None, ylabel=None):
    ax.set_facecolor('white')
    ax.grid(True, axis='y', color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ('top', 'right'):
        ax.spines[side].set_visible(False)
    for side in ('left', 'bottom'):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    if title:  ax.set_title(title, color=INK, fontsize=12, pad=12)
    if xlabel is not None: ax.set_xlabel(xlabel, color=INK_SECONDARY, fontsize=10)
    if ylabel is not None: ax.set_ylabel(ylabel, color=INK_SECONDARY, fontsize=10)
    return ax

RANDOM_STATE = 42


def setting(name, fallback):
    import glb
    value = getattr(glb, name, None)
    return fallback if value is None else value


def seed():
    return int(setting('random_seed', RANDOM_STATE))

def corrected_data_analysis(raw_data_folder, corrected_outputs, sample_id_column, full_calculation, suffix, method, study_name, factor_of_interest):
    import os
    import pandas as pd
    for file in os.listdir(corrected_outputs):
        if file.endswith(f"{suffix}.csv"):
            file_path = os.path.join(corrected_outputs, file)
            corrected_data = pd.read_csv(file_path, low_memory=False)
            try:
                corrected_data = corrected_data.rename(columns={"Unnamed: 0": sample_id_column})
            except:pass
            corrected_data = corrected_data.set_index(sample_id_column)
            full_calculation = after_correction(raw_data_folder, sample_id_column, corrected_data, full_calculation, method=method, file=file.replace(suffix, ""), study_name=study_name, factor_of_interest=factor_of_interest)
    return full_calculation

def run_R(bernard_folder, R):
    bernard_folder = os.path.dirname(os.path.abspath(__file__))
    import subprocess
    r_script = f"{bernard_folder}/{R}"  # Full path to the R script
    # Check script is executable
    #subprocess.run(["chmod", "+x", r_script], check=True)
    subprocess.run(["Rscript", 
                    r_script, 
                    glb.bernard_folder], 
                   check=True)

def after_correction(raw_data_folder, sample_id_column, corrected_data, full_calculation, method, file, study_name, factor_of_interest):
    import pandas as pd
    from workflows import workflow_for_corrected
    #Loading metadata
    metadata = pd.read_csv(f"{raw_data_folder}/metadata.csv").set_index(sample_id_column)
    covariates = [study_name, factor_of_interest]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            metadata_list = [line.strip() for line in covariate_file]
            print("Metadata:", metadata_list)
    covariates.extend(metadata_list)
    metadata = metadata[covariates]
    print("Complete metadata shape: ", metadata.shape)
    try:
        corrected_data = corrected_data.rename(columns={"Unnamed: 0": sample_id_column})
    except: pass
    try:
            corrected_data = corrected_data.set_index(sample_id_column)
    except:pass
    print("Clean dataset shape: ", corrected_data.shape)
    metadata = metadata[metadata.index.isin(corrected_data.index)]
    
    # Merging with metadata
    corrected_data = merge_dataframes(metadata, corrected_data)
    # Analysing corrected results
    corrected_calculations = workflow_for_corrected(corrected_data, file, method=method)
    # Adding results to main dataframe
    full_calculation = pd.concat([full_calculation, corrected_calculations], ignore_index=True)
    del corrected_data
    del corrected_calculations
    return full_calculation

def remove_outliers(dataframe, sample_id_column, study_name, factor_of_interest):
    from sklearn.preprocessing import StandardScaler
    from sklearn.ensemble import IsolationForest
    import numpy as np
    import glb

    contamination = getattr(glb, 'outlier_contamination', 0.05) #defined in bernard_cfg.txt
    if contamination <= 0:
        print("Outlier removal is disabled (outlier_contamination is 0).")
        return dataframe

    raw_data_folder = glb.raw_data_folder
    metadata_to_drop = [sample_id_column, study_name, factor_of_interest]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
        metadata_to_drop.extend(line.strip() for line in covariate_file)
    features = dataframe.drop(columns=[col for col in metadata_to_drop if col in dataframe.columns])
    features = features.apply(pd.to_numeric, errors='coerce').fillna(0.0)

    if features.shape[1] == 0 or features.shape[0] < 3:
        print("Not enough numeric data to look for outliers, skipping outlier removal.")
        return dataframe

    features = StandardScaler().fit_transform(features)
    iso = IsolationForest(contamination=contamination, random_state=seed())
    predicted_outliers = iso.fit_predict(features)
    outliers = np.where(predicted_outliers == -1)[0]
    print(f"IsolationForest marked {len(outliers)} of {dataframe.shape[0]} samples as outliers "
          f"(contamination {contamination}). They are removed before cleaning.")
    return dataframe.drop(dataframe.index[outliers])

def cleaning(data_file, filepath, sample_id_column, processing, workflow, output_path, thresholdSamples, thresholdFeatures, study_name, factor_of_interest):
        import pandas as pd
        import glb
        import json
        import sys
        print(f"\nFile name: {data_file}")
        if filepath.endswith(".csv"):
            dataframe = pd.read_csv(filepath, low_memory=False)
        if filepath.endswith(".tsv"):
            dataframe = pd.read_csv(filepath, sep="\t", low_memory=False)
        # Check if all required columns (study_name, factor_of_interest, sample_id_column) are present
        required_columns = [study_name, factor_of_interest, sample_id_column]
        for column in required_columns:
            if column not in dataframe.columns :
                sys.exit(f'"{column}" column is not present')
        for column in required_columns:
            if dataframe[column].isna().any():
                print(f'Warning: dropping rows with NaN in "{column}"')
        dataframe = dataframe.dropna(subset=required_columns)
        
        # Index column must be sample ID which is stored either in column sample_id_column or in column "Unnamed: 0"
        try:
            dataframe = dataframe.set_index("Unnamed: 0")
        except: 
            dataframe = dataframe.set_index(sample_id_column)
            
        dataframe = dataframe.dropna(subset=[study_name, factor_of_interest])

        data_dir = bfiles.split(filepath)['dir'] #returns directory


        dataframe = remove_outliers(dataframe, sample_id_column, study_name, factor_of_interest)
        print("Dataframe shape after outlier removal")
        print(dataframe.shape)

        raw_dict, clean_df, data_cleaning_time = workflow(dataframe, #current raw data file
                                                          processing, #processing message
                                                          data_dir, #directory with raw data file
                                                          data_file, #current raw data file name
                                                          output_path, #storing processed data here
                                                          thresholdSamples, #defined in bernard_cfg.txt
                                                          thresholdFeatures) #defined in bernard_cfg.txt
        del dataframe
        return clean_df, data_file, raw_dict, data_cleaning_time
        # Cleaned dataset is saved to cleaned folder.

def _image_reader(img_path):
    from reportlab.lib.utils import ImageReader
    try:
        return ImageReader(img_path)
    except Exception as error:
        from PIL import Image
        if 'decompression bomb' not in str(error).lower():
            raise
        previous_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = None
        try:
            image = Image.open(img_path)
            image.load()
            image.thumbnail((4000, 4000), Image.LANCZOS)
            print(f"    note: {os.path.basename(img_path)} was oversized and has been downscaled "
                  f"to {image.size[0]}x{image.size[1]} for the report")
            return ImageReader(image)
        finally:
            Image.MAX_IMAGE_PIXELS = previous_limit

def create_pdf(study_name, factor_of_interest, select_thresholdSamples, select_thresholdFeatures, dataset_name, result_table, images, date, image_dir, output_dir):
    import os
    import datetime
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    pdf_path = os.path.join(output_dir, f"{dataset_name}-{date}.pdf") # where and how to save pdf report
    c = canvas.Canvas(pdf_path, pagesize=letter) #create a new blank PDF file at the location pdf_path
    line_height = 12 #height of one line
    run_date = date
    full_date = datetime.datetime.now()
    date = full_date.strftime("%d.%m.%Y") # a date to be dd.mm.yyy
    alpha = float(setting('significance_alpha', 0.05))
    result_table = result_table[result_table['datasetName'] == dataset_name] #extracts only rows belonging to current dataset
    best_methods = result_table.loc[result_table["Best performance"] == "Best performance", "method"].values
    best_method = best_methods[0] if len(best_methods) else "none (no method could be ranked)"
    gate_skipped = False
    if "step-1-skipped" in result_table.columns:
        flags = result_table["step-1-skipped"]
        gate_skipped = bool(pd.to_numeric(flags, errors="coerce").fillna(0).eq(1).any()
                            or flags.astype(str).str.strip().str.lower().eq("true").any())
    gate_warning = ""
    if gate_skipped:
        reasons = result_table.loc[result_table["Best performance"] == "Best performance",
                                   "rejection-reason"].dropna().astype(str).values \
                  if "rejection-reason" in result_table.columns else []
        detail = str(reasons[0]).split(" (")[0] if len(reasons) else "it did not pass step 1"
        gate_warning = f"No method passed step 1 - {detail}."

    def add_title_and_description(): # it adds head (main title and explanaotry text to each page in pdf report)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(90, 750, f"Report for {dataset_name}") #main pdf title
        c.setFont("Helvetica", 8)
        y_position_desc = 730
        for line in [f"Date: {date} ",
                     f"This report contains visualizations generated from analysis of different batch effect correction methods for {dataset_name}."]:
            c.drawString(90, y_position_desc, line)
            y_position_desc -= 14
            # Each line in explanatory text will be for 14 units lower across y axis
        label = "Best batch effect correction method: "
        c.setFont("Helvetica", 8)
        c.drawString(90, y_position_desc, label)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(90 + c.stringWidth(label, "Helvetica", 8), y_position_desc, f"{best_method}.")
        c.setFont("Helvetica", 8)
        if gate_skipped:
            c.setFillColor(colors.HexColor(PALETTE[7]))
            c.drawString(90 + c.stringWidth(label, "Helvetica", 8)
                         + c.stringWidth(f"{best_method}.", "Helvetica-Bold", 8) + 6,
                         y_position_desc, gate_warning)
            c.setFillColor(colors.black)
        y_position_desc -= 14
        return y_position_desc - 20

    def draw_table(c, df, x, y, width=None, font_size=None): # it adds table with specified formatting
        available_width = letter[0] - x - 40
        if width is not None:
            available_width = min(available_width, width)
        first_column = min(110, available_width * 0.28)
        other_columns = (available_width - first_column) / max(1, len(df.columns) - 1)
        col_widths = [first_column] + [other_columns] * (len(df.columns) - 1)
        # Convert a pandas DataFrame into a list-of-lists that represents a table.
        data = [df.columns.tolist()] + df.values.tolist()
        # Create a ReportLab Table object from it, specifying the column widths
        table = Table(data, colWidths=col_widths) # adds an empty table without formating
        # Table styling
        style = TableStyle([
            # ('COMMAND', (starting column, starting row), (finishing column, finishing row), line thickness, line color)
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),  # Line below header
            ('LINEAFTER', (0, 1), (0, -1), 1, colors.black),  # Line after first column
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),  # Header background
            ('FONTSIZE', (0, 0), (-1, -1), font_size or (5 if other_columns >= 42 else 4)),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black), # Header text color
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'), # Left alignment of text
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # # Bold header font
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10), # Adds space below header text
            ('BACKGROUND', (0, 1), (-1, -1), colors.white) # Background for data rows
        ])
        table.setStyle(style) #include formatting in the existing table
        table_width, table_height = table.wrapOn(c, 500, 700)
        table.drawOn(c, x, y - table_height)
        return y - table_height - 20 # new starting point for the next content

    def draw_key(y, rows, header=("What to read", "A good result"), width=430, x=90):
        key = pd.DataFrame(list(rows), columns=list(header))
        return draw_table(c, key, x, y, width=width, font_size=7)

    def table_page(heading, key_rows, df, key_header=("What to read", "A good result")):
        c.showPage() # new blank page
        y = add_title_and_description() # adds main title and explanatory text at the beginning of the new page
        c.setFont("Helvetica-Bold", 10)
        c.drawString(90, y, heading)
        y -= 2 * line_height
        if key_rows:
            y = draw_key(y, key_rows, header=key_header)
        c.setFont("Helvetica", 5)
        return draw_table(c, df, 90, y)

    def columns_for(prefix, covariate):
        selected = ["datasetName"]
        selected += [col for col in result_table.columns if col.startswith(prefix) and covariate in col]
        selected += ["method"]
        table = result_table[selected]
        table.columns = table.columns.str.replace(rf'{prefix}-', '', regex=True)
        table.columns = table.columns.str.replace(r'-corrected', '\n(corrected)', regex=True) #splits column name in multiple rows
        table.columns = table.columns.str.replace(rf'{covariate}-', f'{covariate}\n', regex=True) #splits column name in multiple rows
        table = table.rename(columns={"datasetName": "Dataset"}) #renames datasetName column name
        return table

    def draw_image(img_file, max_width, max_height, y, x=None):
        img_path = os.path.join(image_dir, img_file) #path to image
        reader = _image_reader(img_path)
        source_width, source_height = reader.getSize()
        scale = min(max_width / source_width, max_height / source_height)
        width, height = source_width * scale, source_height * scale
        draw_x = (letter[0] - width) / 2 if x is None else x
        c.drawImage(reader, draw_x, y - height, width=width, height=height) #insert image
        return y - height

    def is_batch(covariate):
        return covariate == study_name

    y_position = add_title_and_description() #inserts main heading, explanatory text and returns y position for the following content
    c.setFont("Helvetica-Bold", 10) #format for subtitle
    c.drawString(90, y_position, "Batch and phenotype distribution:") #subtitle
    y_position -= 2*line_height #space between subtitle and pie charts
    for img_file in images: #images is a list of png files linked to one specific dataset
        if img_file.startswith("pie-chart-raw"):
            y_position = draw_image(img_file, 560, 190, y_position)

    if "design-balance-cramers-v" in result_table.columns:
        balance_rows = result_table["design-balance-cramers-v"].dropna()
        if len(balance_rows):

            def first_value(column):
                if column not in result_table.columns:
                    return None
                values = result_table[column].dropna()
                return values.iloc[0] if len(values) else None

            cramers_v = float(balance_rows.iloc[0])
            p_value = first_value("design-balance-p-value")
            verdict = str(first_value("design-balance-verdict") or "")

            y_position -= 2*line_height
            c.setFont("Helvetica-Bold", 10)
            c.drawString(90, y_position, f"Design balance: {study_name} against {factor_of_interest}")
            y_position -= 1.8*line_height

            if p_value is None:
                chi_squared_line = ("Chi-squared test", "not available", "")
            elif float(p_value) < alpha:
                printed = "p < 0.001" if float(p_value) < 0.001 else f"p = {float(p_value):.4g}"
                chi_squared_line = ("Chi-squared test", printed,
                                    f"{study_name} and {factor_of_interest} are associated")
            else:
                chi_squared_line = ("Chi-squared test", f"p = {float(p_value):.4g}",
                                    f"no association between {study_name} and {factor_of_interest}")
            for label, value, meaning in [chi_squared_line,
                                          ("Cramer's V", f"{cramers_v:.3f}", verdict)]:
                c.setFont("Helvetica-Bold", 8)
                c.drawString(90, y_position, label)
                c.drawString(190, y_position, value)
                c.setFont("Helvetica", 8)
                c.drawString(265, y_position, meaning)
                y_position -= 1.3*line_height

            y_position -= 0.6*line_height
            y_position = draw_key(y_position,
                                  [("below 0.1", "balanced"),
                                   ("0.1 to 0.3", "weak association, correction is safe"),
                                   ("0.3 to 0.5", "moderate association, interpret the corrected data with care"),
                                   ("above 0.5", "strong association, part of the biology will be removed with the batch")],
                                  header=("Cramer's V", "Meaning"), width=400)

            for img_file in images:
                if img_file.startswith("pie-chart-balance-raw"):
                    y_position = draw_image(img_file, 545, 185, y_position)
                    break

    results_1 = result_table[["datasetName",
                              "initial number of samples",
                              "initial number of features",
                              "new number of samples",
                              "new number of features",
                              "percentage of removed samples",
                              "percentage of removed features"]] #which columns to keep from full excel table
    results_1 = results_1.rename(columns={"datasetName": "Dataset",
                                          "initial number of samples": "Samples\n(raw)",
                                          "initial number of features": "Variables\n(raw)",
                                          "new number of samples": "Samples\n(new)",
                                          "new number of features": "Variables\n(new)",
                                          "percentage of removed samples": "Removed\nsamples\n(%)",
                                          "percentage of removed features": "Removed\nfeatures\n(%)"}) #renaming column names for table in report
    y_position = table_page("Effect of preprocessing:", None, results_1.iloc[:1])
    c.setFont("Helvetica", 10)
    c.drawString(90, y_position - 1.5*line_height, f"Samples with more than {select_thresholdSamples * 100}% zero values were removed.")
    c.drawString(90, y_position - 3*line_height, f"Features with more than {select_thresholdFeatures * 100}% zero values were removed.")

    def selection_page():
        candidates = result_table[result_table["method"].notna() &
                                  (result_table["method"].astype(str) != "uncorrected")]
        if candidates.empty:
            return
        names = [str(value) for value in candidates["method"]]
        if "accepted" in candidates.columns:
            passed = pd.to_numeric(candidates["accepted"], errors="coerce").fillna(0) == 1
        elif "final-rank" in candidates.columns:
            passed = pd.to_numeric(candidates["final-rank"], errors="coerce").fillna(0) > 0
        else:
            passed = pd.Series(True, index=candidates.index)
        rejected = [str(value) for value in candidates.loc[~passed.values, "method"]]
        if "final-rank" in candidates.columns:
            places = pd.to_numeric(candidates["final-rank"], errors="coerce").fillna(0)
            ranked = candidates[places > 0].sort_values("final-rank")
        else:
            ranked = candidates.loc[passed.values]

        reason_counts = {}
        if "rejection-reason" in candidates.columns:
            for reason in candidates.loc[~passed.values, "rejection-reason"].dropna():
                short = str(reason).split(" (")[0]
                reason_counts[short] = reason_counts.get(short, 0) + 1

        c.showPage()
        y = add_title_and_description()
        c.setFont("Helvetica-Bold", 10)
        c.drawString(90, y, "How the method was chosen:")
        y -= 2*line_height

        flow_x, flow_width = 90, 300
        list_x, list_width = 410, 162
        pad = 8
        ink = colors.HexColor(INK)
        quiet = colors.HexColor(INK_SECONDARY)
        rule = colors.HexColor(GRID)

        def chip_layout(items, width, font_size=7):
            rows, row, used = [], [], 0.0
            for text in items:
                chip_width = c.stringWidth(text, "Helvetica", font_size) + 8
                if row and used + chip_width > width:
                    rows.append(row)
                    row, used = [], 0.0
                row.append((text, chip_width))
                used += chip_width + 5
            if row:
                rows.append(row)
            return rows

        def draw_stage(y_top, title, subtitle, items, struck=()):
            rows = chip_layout(items, flow_width - 2*pad)
            height = pad + 11 + (10 if subtitle else 0) + 13*len(rows) + pad
            c.setStrokeColor(rule)
            c.setFillColor(colors.white)
            c.setLineWidth(0.8)
            c.roundRect(flow_x, y_top - height, flow_width, height, 4, stroke=1, fill=1)
            y_line = y_top - pad - 8
            c.setFillColor(ink)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(flow_x + pad, y_line, title)
            y_line -= 11
            if subtitle:
                c.setFillColor(quiet)
                c.setFont("Helvetica", 6.5)
                c.drawString(flow_x + pad, y_line, subtitle)
                y_line -= 10
            for row in rows:
                x = flow_x + pad
                for text, chip_width in row:
                    crossed = text in struck
                    c.setFillColor(colors.HexColor('#f4f4f1') if crossed else colors.HexColor('#eaf1fb'))
                    c.roundRect(x, y_line - 2.5, chip_width, 11, 2, stroke=0, fill=1)
                    c.setFillColor(quiet if crossed else ink)
                    c.setFont("Helvetica", 7)
                    c.drawString(x + 4, y_line, text)
                    if crossed:
                        c.setStrokeColor(colors.HexColor(PALETTE[7]))
                        c.setLineWidth(0.9)
                        c.line(x + 3, y_line + 2.5, x + chip_width - 3, y_line + 2.5)
                        c.setStrokeColor(rule)
                    x += chip_width + 5
                y_line -= 13
            c.setFillColor(colors.black)
            return y_top - height

        def draw_arrow(y_top, x_centre):
            c.setStrokeColor(quiet)
            c.setLineWidth(0.9)
            c.line(x_centre, y_top, x_centre, y_top - 10)
            head = c.beginPath()
            head.moveTo(x_centre - 3, y_top - 10)
            head.lineTo(x_centre + 3, y_top - 10)
            head.lineTo(x_centre, y_top - 15)
            head.close()
            c.setFillColor(quiet)
            c.drawPath(head, stroke=0, fill=1)
            c.setFillColor(colors.black)
            return y_top - 18

        def draw_ranking(y_top):
            rows = [row for _, row in ranked.iterrows()]
            height = pad + 13 + 12*max(len(rows), 1) + pad
            c.setStrokeColor(rule)
            c.setFillColor(colors.white)
            c.setLineWidth(0.8)
            c.roundRect(list_x, y_top - height, list_width, height, 4, stroke=1, fill=1)
            y_line = y_top - pad - 8
            c.setFillColor(ink)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(list_x + pad, y_line, "Final ranking")
            y_line -= 13
            if not rows:
                c.setFont("Helvetica", 7)
                c.setFillColor(quiet)
                c.drawString(list_x + pad, y_line, "no method could be ranked")
                c.setFillColor(colors.black)
                return
            for position, row in enumerate(rows, start=1):
                name = str(row["method"])
                score = row.get("consensus-score")
                best = position == 1
                c.setFillColor(ink if best else quiet)
                c.setFont("Helvetica-Bold" if best else "Helvetica", 7)
                c.drawString(list_x + pad, y_line, f"{position}.")
                c.drawString(list_x + pad + 14, y_line, name)
                if score is not None and pd.notna(score):
                    c.drawRightString(list_x + list_width - pad, y_line, f"{float(score):.0f}")
                y_line -= 12
            c.setFillColor(colors.black)

        y = draw_stage(y, f"{len(names)} correction methods produced a corrected dataset",
                       "every method that finished on this dataset", names)
        y = draw_arrow(y - 4, flow_x + flow_width/2)
        y = draw_stage(y, "Step 1 - PERMANOVA gate",
                       f"kept: {study_name} p > {alpha} and {factor_of_interest} p < {alpha}",
                       names, struck=rejected)
        if reason_counts:
            c.setFont("Helvetica", 6.5)
            c.setFillColor(quiet)
            for reason, count in sorted(reason_counts.items(), key=lambda item: -item[1]):
                y -= 9
                c.drawString(flow_x + 10, y, f"crossed out - {reason} ({count})")
            c.setFillColor(colors.black)
        if gate_skipped:
            y -= 9
            c.setFont("Helvetica-Bold", 6.5)
            c.setFillColor(colors.HexColor(PALETTE[7]))
            c.drawString(flow_x + 10, y, "no method passed - step 1 skipped, all methods ranked")
            c.setFillColor(colors.black)
        y = draw_arrow(y - 4, flow_x + flow_width/2)
        y = draw_stage(y, f"Steps 2 to 4 - {len(ranked)} methods ranked on 21 measures",
                       "each measure ordered best to worst, the places turned into points and added up",
                       [str(value) for value in ranked["method"]])
        y = draw_arrow(y - 4, flow_x + flow_width/2)
        ranking_top = y
        y = draw_stage(y, "Step 5 - the highest total wins",
                       "equal totals are separated on the leftover batch variability",
                       [str(best_method)] if len(ranked) else ["no winner"])
        arrow_y = (ranking_top + y) / 2
        c.setStrokeColor(quiet)
        c.setLineWidth(0.9)
        c.line(flow_x + flow_width, arrow_y, list_x - 6, arrow_y)
        head = c.beginPath()
        head.moveTo(list_x - 6, arrow_y + 3)
        head.lineTo(list_x - 6, arrow_y - 3)
        head.lineTo(list_x, arrow_y)
        head.close()
        c.setFillColor(quiet)
        c.drawPath(head, stroke=0, fill=1)
        c.setFillColor(colors.black)
        draw_ranking(ranking_top)

    selection_page()

    for covariate in [study_name, factor_of_interest]:
        key = [("R2 (corrected)", "as low as possible - the batches no longer explain the data"),
               ("p-value (corrected)", f"above {alpha} - the batches no longer separate")] if is_batch(covariate) else \
              [("R2 (corrected)", "as close to the raw R2 as possible - the biology is kept"),
               ("p-value (corrected)", f"below {alpha} - the groups still separate")]
        table_page(f"PERMANOVA results for {covariate}:", key, columns_for('permanova', covariate))

    permdisp_columns_all = [col for col in result_table.columns if col.startswith('permdisp')]
    if permdisp_columns_all:
        for covariate in [study_name, factor_of_interest]:
            table_page(f"PERMDISP results for {covariate} (multivariate dispersion):",
                       [("p-value (corrected)", f"above {alpha} - the PERMANOVA R2 is a difference between group centroids"),
                        ("PERMANOVA and PERMDISP both significant", "the R2 is confounded by dispersion")],
                       columns_for('permdisp', covariate))

    silhouette_columns_all = [col for col in result_table.columns if col.startswith('silhouette')]
    if silhouette_columns_all:
        for covariate in [study_name, factor_of_interest]:
            key = [("silhouette (corrected)", "as low as possible - samples of different batches are mixed")] \
                if is_batch(covariate) else \
                [("silhouette (corrected)", "as high as possible - samples of one group stay together")]
            table_page(f"Silhouette width for {covariate} (how separated the groups are):",
                       key + [("range", "-1 to 1, comparable between methods and between datasets")],
                       columns_for('silhouette', covariate))

    kbet_columns_all = [col for col in result_table.columns if col.startswith('kBET')]
    if kbet_columns_all:
        for covariate in [study_name, factor_of_interest]:
            key = [("acceptance rate (corrected)", "as high as possible - the batches are mixed locally")] \
                if is_batch(covariate) else \
                [("acceptance rate (corrected)", "as low as possible - the phenotype is not spread evenly")]
            table_page(f"kBET acceptance rate for {covariate} (local mixing):", key,
                       columns_for('kBET', covariate))

    lisi_columns_all = [col for col in result_table.columns
                        if col.startswith(('LISI', 'iLISI', 'cLISI'))]
    if lisi_columns_all:
        for covariate in [study_name, factor_of_interest]:
            name = lisi_name(covariate, study_name, factor_of_interest)
            key = [(f"{name} (corrected)", "as high as possible, up to the number of batches")] \
                if is_batch(covariate) else \
                [(f"{name} (corrected)", "as low as possible, down to 1")]
            table_page(f"{name} for {covariate} (how mixed the neighbourhood of a sample is):", key,
                       columns_for(name, covariate))

    connectivity_columns_all = [col for col in result_table.columns if col.startswith('graph-connectivity')]
    if connectivity_columns_all:
        for covariate in [factor_of_interest, study_name]:
            key = [("connectivity (corrected)", "as low as possible - the batch is no longer one island")] \
                if is_batch(covariate) else \
                [("connectivity (corrected)", "as high as possible - the phenotype is still in one piece")]
            table_page(f"Graph connectivity for {covariate} (are the groups still in one piece):", key,
                       columns_for('graph-connectivity', covariate))

        for marker, when in (("graph-connectivity-raw", "before correction"),
                             ("graph-connectivity-corrected", f"after correction with {best_method}")):
            for img_file in images:
                if img_file.startswith(marker):
                    c.showPage()
                    y_position = add_title_and_description()
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(90, y_position, f"The nearest neighbour graph, {when}:")
                    y_position -= 2*line_height
                    y_position = draw_key(y_position,
                                          [("coloured dot or line", "belongs to the largest connected piece of its group"),
                                           ("hollow grey dot", "did not make it into that piece"),
                                           (f"left panel ({factor_of_interest})", "the coloured web should stay whole after correction"),
                                           (f"right panel ({study_name})", "the islands should fall apart after correction")],
                                          header=("What to read", "Meaning"))
                    draw_image(img_file, 545, 300, y_position)
                    break

    pvca_columns = [col for col in result_table.columns if col.startswith('pvca-')]
    if pvca_columns:
        pvca_table = result_table[["datasetName"] + pvca_columns + ["method"]]
        pvca_table.columns = pvca_table.columns.str.replace(r'pvca-', '', regex=True)
        pvca_table.columns = pvca_table.columns.str.replace(r'-percent-corrected', '\n(corrected)', regex=True)
        pvca_table.columns = pvca_table.columns.str.replace(r'-percent', '', regex=True)
        pvca_table = pvca_table.rename(columns={"datasetName": "Dataset"})
        table_page("Principal Variance Component Analysis (share of variability, %):",
                   [("batch (corrected)", "collapses after correction"),
                    ("phenotype (corrected)", "unchanged after correction"),
                    ("the four shares", "add up to 100%")],
                   pvca_table)

    varpart_columns = [col for col in result_table.columns if col.startswith('varpart-')]
    if varpart_columns:
        varpart_table = result_table[["datasetName"] + varpart_columns + ["method"]]
        varpart_table.columns = varpart_table.columns.str.replace(r'varpart-', '', regex=True)
        varpart_table.columns = varpart_table.columns.str.replace(r'-corrected', '\n(corrected)', regex=True)
        varpart_table = varpart_table.rename(columns={"datasetName": "Dataset"})
        table_page("Variance partitioning (batch only / biology only / shared / unexplained):",
                   [("batch only", "collapses after correction"),
                    ("phenotype only", "holds after correction; both collapsing means the data was flattened"),
                    ("shared", "near zero is a clean design, large means batch and biology are confounded"),
                    ("unexplained", "everything else; small negative values read as zero")],
                   varpart_table)

    feature_columns = [col for col in result_table.columns if col.startswith('features-associated-')]
    if feature_columns:
        feature_table = result_table[["datasetName"] + feature_columns + ["method"]]
        feature_table.columns = feature_table.columns.str.replace(r'features-associated-', '', regex=True)
        feature_table.columns = feature_table.columns.str.replace(r'-percent-corrected', '\n(corrected)', regex=True)
        feature_table.columns = feature_table.columns.str.replace(r'-percent', '', regex=True)
        feature_table = feature_table.rename(columns={"datasetName": "Dataset"})
        table_page("Features still associated with each variable (%, FDR < 0.05):",
                   [(f"{study_name} (corrected)", "drops sharply after correction"),
                    (f"{factor_of_interest} (corrected)", "stays; a drop means the biology was flattened")],
                   feature_table)

    for prefix, heading, batch_key, biology_key, extra in [
        ('alignment-score', "Alignment score (share of neighbours from another group):",
         "as high as possible, up to the max column",
         "as low as possible",
         [("max", "the ceiling of this dataset, set by how many samples each group holds")]),
        ('entropy-score', "Entropy score (how evenly the groups are mixed locally):",
         "as high as possible, 1.00 is every group equally represented",
         "as low as possible",
         [])]:
        columns_present = [col for col in result_table.columns if col.startswith(prefix)]
        if not columns_present:
            continue
        for covariate in [study_name, factor_of_interest]:
            key = [("score (corrected)", batch_key if is_batch(covariate) else biology_key)] + extra
            table_page(f"{heading[:-1]} - {covariate}:", key, columns_for(prefix, covariate))

    auroc_columns_all = [col for col in result_table.columns if col.startswith('AUROC')]
    if auroc_columns_all:
        auroc_table = result_table[["datasetName"] + auroc_columns_all + ["method"]]
        auroc_table.columns = auroc_table.columns.str.replace(r'AUROC-', '', regex=True)
        auroc_table.columns = auroc_table.columns.str.replace(rf'{factor_of_interest}-', f'{factor_of_interest}\n', regex=True) #splits column name in multiple rows
        auroc_table.columns = auroc_table.columns.str.replace(r'-corrected', '\n(corrected)', regex=True) #splits column name in multiple rows
        auroc_table = auroc_table.rename(columns={"datasetName": "Dataset"}) #renames datasetName column name
        table_page(f"Prediction of {factor_of_interest} before and after correction (AUROC):",
                   [("0.5", f"the {factor_of_interest} groups cannot be told apart at all"),
                    ("1.0", "the groups are separated perfectly"),
                    ("cv", "stratified cross validation over all samples pooled together"),
                    ("lobo", "leave one batch out, averaged over the batches")],
                   auroc_table, key_header=("Value", "Meaning"))

        for img_file in images:
            if img_file.startswith("ROC-"):
                c.showPage() # new blank page
                y_position = add_title_and_description()
                c.setFont("Helvetica-Bold", 10)
                c.drawString(90, y_position, "ROC curves before and after correction:")
                y_position -= 2*line_height
                y_position = draw_key(y_position,
                                      [("area under a curve", "the AUROC of the table on the previous page"),
                                       ("a curve on the diagonal", "the groups cannot be told apart at all")],
                                      header=("What to read", "Meaning"))
                draw_image(img_file, 545, 300, y_position)

    for marker, heading, key, key_header in [
        ("batch-dissimilarity",
         "Leftover batch separation, all methods at once:",
         [("near 0", "samples no longer separate by study - the batch effect is gone"),
          ("large", "samples still separate by study - the batch effect remains")],
         ("Bar height", "Meaning")),
        ("feature-r2",
         "How much of each individual feature is explained, all methods at once:",
         [(f"{study_name} boxes", "collapse towards zero after correction"),
          (f"{factor_of_interest} boxes", "stay where they were; both collapsing means the data was flattened"),
          ("the line and the box", "the median feature and the middle half of the features")],
         ("What to read", "A good result")),
        ("variance-partition",
         "Where the variability comes from, all methods at once:",
         [("phenotype only", "what only the biology explains - should survive"),
          ("batch only", "what only the batch explains - should disappear"),
          ("shared", "what both explain equally well - a band that does not shrink is a warning"),
          ("unexplained", "everything else")],
         ("Band", "Meaning"))]:
        for img_file in images:
            if marker in img_file:
                c.showPage()
                y_position = add_title_and_description()
                c.setFont("Helvetica-Bold", 10)
                c.drawString(90, y_position, heading)
                y_position -= 2*line_height
                y_position = draw_key(y_position, key, header=key_header)
                draw_image(img_file, 545, 340, y_position)
                break

    for img_file in images:
        if "stability" in img_file:
            c.showPage()
            y_position = add_title_and_description()
            c.setFont("Helvetica-Bold", 10)
            c.drawString(90, y_position, "Is the chosen method a stable choice?")
            y_position -= 2*line_height
            y_position = draw_key(y_position,
                                  [("left panel", "how often each method was chosen; above 70% is a clear winner"),
                                   ("right panel", "leftover batch variability over the resamples; overlapping bars cannot be separated"),
                                   ("Kendall's W", "1.0 the same ranking every time, above 0.7 strong agreement, near 0 noise")],
                                  header=("What to read", "Meaning"))
            draw_image(img_file, 545, 300, y_position)
            break

    c.showPage() # new blank page
    y_position = add_title_and_description() # adds main title and explanatory text at the beginning of the new page
    c.setFont("Helvetica-Bold", 10)
    c.drawString(90, y_position, "Percentage of variability, explained by batch and factor of interest before and after correction:") #barchart heading
    y_position -= 3*line_height #space between heading and barchart
    for img_file in images:
        if "variability-change" in img_file: # find correct image in the images list
            draw_image(img_file, 545, 470, y_position)

    c.showPage() # new blank page
    y_position = add_title_and_description() # adds main title and explanatory text at the beginning of the new page
    y_position -= line_height # space between explanatory text and first image
    custom_order = ["PCoA-raw", "PCoA-corrected", "PCA-raw", "PCA-corrected",
                    "NMDS-raw", "NMDS-corrected", "TSNE-raw", "TSNE-corrected",
                    "MDS-raw", "MDS-corrected",
                    "dissimilarity-raw", "dissimilarity-corrected"] # define order of 2D plots
    for element in custom_order:
        for img_file in images: # find correct image in the images list
            if img_file.startswith(element):
                width, height = 520, 270
                if y_position < height + 50:
                    c.showPage() # new blank page
                    y_position = add_title_and_description() # adds main title and explanatory text at the beginning of the new page
                y_position = draw_image(img_file, width, height, y_position) - 20

    c.save() #save pdf
    #print(f"Saved PDF: {pdf_path}") #confirm pdf saving

def pie_charts(dataset, output, title):
    bernard_folder = glb.bernard_folder
    raw_data_folder = bernard_folder + "/raw-data"
    import json
    # Define what are names of sample ID, study ID and phenotype columns in config.json file
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])
    #sample_id_column = str(config["sample_id_column"])
    import matplotlib.pyplot as plt
    # Ensure the output directory exists
    fig, axs = plt.subplots(1, 2, figsize=(20, 6))  # Adjusted height for better aspect ratio
    # Pie chart - diagnosis
    diagnosis = dataset[factor_of_interest].value_counts().sort_index()
    diagnosis.plot(kind='pie', autopct='%1.1f%%', startangle=90, ax=axs[0],
                   colors=group_colours(len(diagnosis)), wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    axs[0].set_title(factor_of_interest)
    axs[0].axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    axs[0].set_ylabel('')
    # Pie chart - bioproject
    bioProjects = dataset[study_name].value_counts().sort_index()
    bioProjects.plot(kind='pie', autopct='%1.1f%%', startangle=90, ax=axs[1],
                     colors=group_colours(len(bioProjects)), wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    axs[1].set_title(study_name)
    axs[1].axis('equal')
    axs[1].set_ylabel('')
    plt.tight_layout()
    plt.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)))

def phenotype_pie_per_batch(dataset, output, title):
    import json
    import math
    import matplotlib.pyplot as plt
    import pandas as pd

    raw_data_folder = glb.bernard_folder + "/raw-data"
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])

    if study_name not in dataset.columns or factor_of_interest not in dataset.columns:
        print(f"The pie per {study_name} was skipped: the dataset does not carry both columns.")
        return None
    counts = pd.crosstab(dataset[study_name].astype(str), dataset[factor_of_interest].astype(str))
    if counts.empty:
        return None
    batches = list(counts.index)
    if len(batches) > 30:
        print(f"The pie per {study_name} was skipped: {len(batches)} groups are too many to draw.")
        return None

    phenotypes = list(counts.columns)
    colours = dict(zip(phenotypes, group_colours(len(phenotypes))))

    columns = min(5, len(batches))
    rows = int(math.ceil(len(batches) / columns))
    figure, axes = plt.subplots(rows, columns, figsize=(3.6 * columns, 4.0 * rows), squeeze=False)
    for position, batch in enumerate(batches):
        axis = axes[position // columns][position % columns]
        share = counts.loc[batch]
        present = share[share > 0]
        axis.pie(present.values, autopct='%1.1f%%', startangle=90,
                 colors=[colours[name] for name in present.index],
                 wedgeprops={'edgecolor': 'white', 'linewidth': 2},
                 textprops={'fontsize': 9, 'color': 'white'})
        axis.set_title(f"{batch}  (n = {int(share.sum())})", color=INK, fontsize=11)
        axis.axis('equal')
    for empty in range(len(batches), rows * columns):
        axes[empty // columns][empty % columns].axis('off')

    from matplotlib.patches import Patch
    figure.legend(handles=[Patch(facecolor=colours[name], label=str(name)) for name in phenotypes],
                  loc='lower center', ncol=min(len(phenotypes), 6), frameon=False,
                  fontsize=10, labelcolor=INK_SECONDARY)
    figure.suptitle(f"{factor_of_interest} in each {study_name}", color=INK, fontsize=13)
    figure.tight_layout(rect=(0, 0.06, 1, 1))
    figure.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)))
    plt.close(figure)
    return counts

def merge_dataframes(df1, df2):
    import pandas as pd
    # Concatenate the dataframes along the index
    merged_df = pd.concat([df1, df2], axis=0)
    # Group by the index and aggregate the values
    merged_df = merged_df.groupby(merged_df.index).first()
    return merged_df

def _transform_for_evaluation(values):
    import numpy as np
    import glb

    space = str(getattr(glb, 'evaluation_space', 'zscore-euclidean')).lower()
    values = np.asarray(values, dtype=float)

    if space == 'euclidean':
        return values, 'euclidean'

    if space == 'zscore-euclidean':
        standard_deviation = values.std(axis=0)
        values = values[:, standard_deviation > 0]
        standard_deviation = standard_deviation[standard_deviation > 0]
        if values.shape[1] == 0:
            return values, 'euclidean'
        values = (values - values.mean(axis=0)) / standard_deviation
        return values, 'euclidean'

    minimum = values.min() if values.size else 0.0
    if minimum < 0:
        values = values - minimum

    if space == 'braycurtis':
        if (values.sum(axis=1) == 0).any():
            values = values + 1e-12
        return values, 'braycurtis'

    if space == 'aitchison':
        log_values = np.log(values + 1.0)
        values = log_values - log_values.mean(axis=1, keepdims=True)
        return values, 'euclidean'

    raise ValueError(f"Unknown evaluation_space '{space}'. Use zscore-euclidean, aitchison, braycurtis or euclidean.")

def _prepare_for_distance_tests(df, feature):
    import json
    import pandas as pd
    from scipy.spatial.distance import pdist, squareform
    from skbio.stats.distance import DistanceMatrix
    import glb
    raw_data_folder = glb.raw_data_folder

    # Define what are names of sample ID, study ID and phenotype columns in config.json file
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])

    prepared_df = df.copy()
    prepared_df.columns = prepared_df.columns.astype(str)

    to_drop = [study_name, factor_of_interest]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            metadata = [line.strip() for line in covariate_file]
    to_drop.extend(metadata)
    if feature in to_drop:
        to_drop.remove(feature) # only column with metadata being currently analysed needs to be included in the dataframe
    prepared_df = prepared_df.drop(columns=[col for col in to_drop if col in prepared_df.columns], errors='raise')

    if feature in prepared_df.columns:
        prepared_df = prepared_df.dropna(subset=[feature]) #removing all rows where currently analysed feature has NaN
    else:
        print(f"\nFeature '{feature}' not found after dropping columns. Skipping this feature.")
        return None

    prepared_df['labels'], _ = pd.factorize(prepared_df[feature]) #converting categorical variable into numeric labels in new column "labels"
    prepared_df = prepared_df.drop(columns=[feature]) #removes original columns with categorical variables
    original_indices = prepared_df.index
    independent_variables = prepared_df.drop(columns=['labels'])
    independent_variables = independent_variables.apply(pd.to_numeric, errors='coerce')
    non_numeric = independent_variables.columns[independent_variables.isna().all()]
    if len(non_numeric):
        print(f"\n{len(non_numeric)} column(s) hold no numeric value and are left out of the "
              f"distance calculation: {', '.join(map(str, non_numeric[:5]))}"
              f"{' ...' if len(non_numeric) > 5 else ''}")
        independent_variables = independent_variables.drop(columns=non_numeric)
    independent_variables = independent_variables.fillna(0.0).astype(float)
    values, metric = _transform_for_evaluation(independent_variables.values)
    distance_matrix = squareform(pdist(values, metric=metric))
    distance_matrix_object = DistanceMatrix(distance_matrix, ids=original_indices.astype(str))
    return distance_matrix, distance_matrix_object, prepared_df['labels']

def _seed_kwargs(skbio_function):
    import inspect
    import numpy as np
    np.random.seed(RANDOM_STATE)
    if 'seed' in inspect.signature(skbio_function).parameters:
        return {'seed': RANDOM_STATE}
    return {}

def _permanova_from_distance(distance_matrix, distance_matrix_object, labels):
    import numpy as np
    from skbio.stats.distance import permanova as skbio_permanova
    # PERMANOVA tests if the distances between samples differ significantly between groups more than within groups?
    result = skbio_permanova(distance_matrix_object,
                             grouping=labels,
                             permutations=int(setting('permanova_permutations', 999)),
                             **_seed_kwargs(skbio_permanova))
    FStatistics = str(result['test statistic'])
    pValue = str(result['p-value'])
    # R2 score calculation
    ss_total = np.sum(distance_matrix ** 2) / distance_matrix.shape[0] #total multivariate dispersion
    # Within-group sum of squares
    ss_within = 0 #dispersion inside each groups
    label_values = labels.values
    # Dispersion is computed in each group separately
    for group in np.unique(label_values):
        group_idx = np.where(label_values == group)[0]
        if len(group_idx) > 1:
            group_dist = distance_matrix[np.ix_(group_idx, group_idx)]
            ss_within += np.sum(group_dist ** 2) / len(group_idx)
    ss_between = ss_total - ss_within #variation explained by grouping factor
    R2 = ss_between / ss_total #R2 equation
    return pValue, FStatistics, R2

_permdisp_ordination_cache = {}
_permdisp_accepts_ordination = True

def _permdisp_ordination(distance_matrix_object):
    import hashlib
    import numpy as np
    from skbio.stats.ordination import pcoa
    data = np.ascontiguousarray(distance_matrix_object.data)
    key = (data.shape, hashlib.sha1(data).hexdigest())
    ordination = _permdisp_ordination_cache.get(key)
    if ordination is None:
        _permdisp_ordination_cache.clear()
        try:
            ordination = pcoa(distance_matrix_object, method='eigh', number_of_dimensions=0)
        except TypeError:
            ordination = pcoa(distance_matrix_object)
        _permdisp_ordination_cache[key] = ordination
    if 'grouping' in ordination.samples.columns:
        ordination.samples = ordination.samples.drop(columns='grouping')
    return ordination

def _permdisp_from_distance(distance_matrix_object, labels):
    global _permdisp_accepts_ordination
    import glb
    from skbio.stats.distance import permdisp as skbio_permdisp
    permutations = getattr(glb, 'permdisp_permutations', 999)
    test = str(getattr(glb, 'permdisp_test', 'median'))
    arguments = dict(grouping=labels,
                     test=test,
                     permutations=permutations,
                     **_seed_kwargs(skbio_permdisp))
    result = None
    if _permdisp_accepts_ordination:
        try:
            result = skbio_permdisp(_permdisp_ordination(distance_matrix_object), **arguments)
        except TypeError:
            _permdisp_accepts_ordination = False
    if result is None:
        result = skbio_permdisp(distance_matrix_object, **arguments)
    FStatistics = str(result['test statistic'])
    pValue = str(result['p-value'])
    return pValue, FStatistics

def _silhouette_from_distance(distance_matrix, labels):
    from sklearn.metrics import silhouette_score
    import numpy as np
    label_values = np.asarray(labels)
    number_of_groups = len(np.unique(label_values))
    if number_of_groups < 2 or number_of_groups >= len(label_values):
        return None
    try:
        return float(silhouette_score(distance_matrix, label_values, metric='precomputed'))
    except Exception as e:
        print(f"Silhouette width could not be calculated: {e}")
        return None

def silhouette(df, feature):
    prepared = _prepare_for_distance_tests(df, feature)
    if prepared is None:
        return None
    distance_matrix, _, labels = prepared
    return _silhouette_from_distance(distance_matrix, labels)

def _knn_indices_from_distance(distance_matrix, k):
    import numpy as np
    number_of_samples = distance_matrix.shape[0]
    k = int(min(k, number_of_samples - 1))
    if k < 1:
        return None
    order = np.argsort(distance_matrix, axis=1, kind='stable')[:, :k + 1]
    neighbours = np.empty((number_of_samples, k), dtype=int)
    for sample in range(number_of_samples):
        row = order[sample]
        neighbours[sample] = row[row != sample][:k]
    return neighbours

def _kbet_from_distance(distance_matrix, labels, k, alpha=None):
    import numpy as np
    from scipy.stats import chi2

    if alpha is None:
        alpha = float(setting('kbet_alpha', 0.05))

    label_values = np.asarray(labels)
    groups, group_sizes = np.unique(label_values, return_counts=True)
    if len(groups) < 2:
        return None
    neighbours = _knn_indices_from_distance(distance_matrix, k)
    if neighbours is None:
        return None

    neighbourhood_size = neighbours.shape[1] + 1
    expected = (group_sizes / len(label_values)) * neighbourhood_size
    degrees_of_freedom = len(groups) - 1

    accepted = 0
    for sample in range(len(label_values)):
        in_neighbourhood = np.append(label_values[neighbours[sample]], label_values[sample])
        observed = np.array([(in_neighbourhood == group).sum() for group in groups], dtype=float)
        statistic = float(np.sum((observed - expected) ** 2 / expected))
        if float(chi2.sf(statistic, degrees_of_freedom)) > alpha:
            accepted += 1
    return accepted / len(label_values)

def _gaussian_kernel_weights(distances, log_perplexity, iterations=50, tolerance=1e-5):
    import numpy as np
    beta = 1.0
    beta_min, beta_max = -np.inf, np.inf
    weights = None
    for _ in range(iterations):
        weights = np.exp(-distances * beta)
        total = weights.sum()
        if not np.isfinite(total) or total <= 0:
            return None
        entropy = np.log(total) + beta * float((distances * weights).sum()) / total
        difference = entropy - log_perplexity
        if abs(difference) < tolerance:
            break
        if difference > 0:
            beta_min = beta
            beta = beta * 2 if beta_max == np.inf else (beta + beta_max) / 2
        else:
            beta_max = beta
            beta = beta / 2 if beta_min == -np.inf else (beta + beta_min) / 2
    total = weights.sum()
    if total <= 0:
        return None
    return weights / total

def _lisi_from_distance(distance_matrix, labels, k):
    import numpy as np
    label_values = np.asarray(labels)
    groups = np.unique(label_values)
    if len(groups) < 2:
        return None
    neighbours = _knn_indices_from_distance(distance_matrix, k)
    if neighbours is None:
        return None

    log_perplexity = np.log(max(neighbours.shape[1] / 3.0, 1.0))

    local_diversity = []
    for sample in range(len(label_values)):
        distances = distance_matrix[sample, neighbours[sample]].astype(float)
        weights = _gaussian_kernel_weights(distances, log_perplexity)
        if weights is None:
            continue
        neighbour_labels = label_values[neighbours[sample]]
        simpson = float(sum(weights[neighbour_labels == group].sum() ** 2 for group in groups))
        if simpson <= 0:
            continue
        local_diversity.append(1.0 / simpson)
    if not local_diversity:
        return None
    return float(np.median(local_diversity))

def _graph_connectivity_from_distance(distance_matrix, labels, k):
    import numpy as np
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    label_values = np.asarray(labels)
    groups = np.unique(label_values)
    if len(groups) < 2:
        return None
    neighbours = _knn_indices_from_distance(distance_matrix, k)
    if neighbours is None:
        return None

    number_of_samples = len(label_values)
    rows = np.repeat(np.arange(number_of_samples), neighbours.shape[1])
    columns = neighbours.reshape(-1)
    graph = csr_matrix((np.ones(len(rows)), (rows, columns)),
                       shape=(number_of_samples, number_of_samples))
    graph = graph.maximum(graph.T)

    connected_share = []
    for group in groups:
        in_group = np.where(label_values == group)[0]
        if len(in_group) < 2:
            continue
        subgraph = graph[in_group][:, in_group]
        _, piece_of_sample = connected_components(subgraph, directed=False)
        largest_piece = np.bincount(piece_of_sample).max()
        connected_share.append(largest_piece / len(in_group))
    if not connected_share:
        return None
    return float(np.mean(connected_share))

def graph_connectivity_plot(df, features, output, title, k=None):
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components
    import glb

    if isinstance(features, str):
        features = [features]
    if k is None:
        k = int(getattr(glb, 'neighbourhood_k', 30))

    def flat_layout(distance_matrix):
        number_of_samples = distance_matrix.shape[0]
        gram = np.asarray(distance_matrix, dtype=float) ** 2
        gram -= gram.mean(axis=1, keepdims=True)
        gram -= gram.mean(axis=0, keepdims=True)
        gram *= -0.5
        gram = (gram + gram.T) / 2.0

        eigenvalues = eigenvectors = None
        if number_of_samples > 1500:
            try:
                from scipy.sparse.linalg import eigsh
                eigenvalues, eigenvectors = eigsh(gram, k=2, which='LA')
            except Exception as e:
                print(f"The graph layout fell back to the full decomposition: {e}")
        if eigenvalues is None:
            eigenvalues, eigenvectors = np.linalg.eigh(gram)
        leading = np.argsort(eigenvalues)[::-1][:2]
        return eigenvectors[:, leading] * np.sqrt(np.clip(eigenvalues[leading], 0.0, None))

    panels = []
    for feature in features:
        prepared = _prepare_for_distance_tests(df, feature)
        if prepared is None:
            continue
        distance_matrix, _, labels = prepared
        label_values = np.asarray(labels)
        groups = np.unique(label_values)
        if len(groups) < 2:
            print(f"Graph connectivity picture skipped for {feature}: it has fewer than two groups.")
            continue
        neighbours = _knn_indices_from_distance(distance_matrix, k)
        if neighbours is None:
            print(f"Graph connectivity picture skipped for {feature}: too few samples for {k} neighbours.")
            continue

        number_of_samples = len(label_values)
        rows = np.repeat(np.arange(number_of_samples), neighbours.shape[1])
        columns = neighbours.reshape(-1)
        graph = csr_matrix((np.ones(len(rows)), (rows, columns)),
                           shape=(number_of_samples, number_of_samples))
        graph = graph.maximum(graph.T)

        in_largest = np.zeros(number_of_samples, dtype=bool)
        share_of_group = {}
        for group in groups:
            in_group = np.where(label_values == group)[0]
            if len(in_group) < 2:
                continue
            subgraph = graph[in_group][:, in_group]
            _, piece_of_sample = connected_components(subgraph, directed=False)
            sizes = np.bincount(piece_of_sample)
            largest = int(np.argmax(sizes))
            in_largest[in_group[piece_of_sample == largest]] = True
            share_of_group[group] = float(sizes[largest] / len(in_group))
        if not share_of_group:
            continue

        pairs = graph.tocoo()
        inside = (pairs.row < pairs.col) & (label_values[pairs.row] == label_values[pairs.col])
        edge_from, edge_to = pairs.row[inside], pairs.col[inside]
        joins_largest = in_largest[edge_from] & in_largest[edge_to]

        names = []
        if feature in df.columns:
            names = [str(name) for name in pd.factorize(df[feature].dropna())[1]]

        panels.append({'feature': feature,
                       'coordinates': flat_layout(distance_matrix),
                       'labels': label_values,
                       'groups': groups,
                       'names': names,
                       'in_largest': in_largest,
                       'edge_from': edge_from,
                       'edge_to': edge_to,
                       'joins_largest': joins_largest,
                       'share_of_group': share_of_group})

    if not panels:
        print("Graph connectivity picture skipped: no grouping could be drawn.")
        return None

    figure, axes = plt.subplots(1, len(panels), figsize=(8 * len(panels), 7), squeeze=False)
    connectivity = {}
    for axis, panel in zip(axes[0], panels):
        coordinates = panel['coordinates']
        label_values, groups = panel['labels'], panel['groups']
        colours = group_colours(len(groups))
        markers = group_markers(len(groups))
        by_name = {name: position for position, name in enumerate(sorted(panel['names']))}
        position_of = {}
        for index, group in enumerate(groups):
            name = panel['names'][int(group)] if int(group) < len(panel['names']) else None
            position_of[group] = by_name.get(name, index)

        loose = [[coordinates[a], coordinates[b]] for a, b
                 in zip(panel['edge_from'][~panel['joins_largest']],
                        panel['edge_to'][~panel['joins_largest']])]
        if loose:
            axis.add_collection(LineCollection(loose, colors=GRID, linewidths=0.5, zorder=1))
        outside = ~panel['in_largest']
        if outside.any():
            axis.scatter(coordinates[outside, 0], coordinates[outside, 1], s=26,
                         facecolors='none', edgecolors=NEUTRAL, linewidths=0.8, zorder=3)

        handles = []
        for group in groups:
            index = position_of[group]
            name = panel['names'][int(group)] if int(group) < len(panel['names']) else str(group)
            share = panel['share_of_group'].get(group)
            of_this_group = panel['joins_largest'] & (label_values[panel['edge_from']] == group)
            segments = [[coordinates[a], coordinates[b]] for a, b
                        in zip(panel['edge_from'][of_this_group], panel['edge_to'][of_this_group])]
            if segments:
                axis.add_collection(LineCollection(segments, colors=colours[index],
                                                   linewidths=0.9, alpha=0.55, zorder=2))
            drawn = panel['in_largest'] & (label_values == group)
            if drawn.any():
                axis.scatter(coordinates[drawn, 0], coordinates[drawn, 1], s=34,
                             color=colours[index], marker=markers[index],
                             edgecolors='white', linewidths=0.4, zorder=4)
            label = name if share is None else f"{name} - {share * 100:.0f}% in one piece"
            handles.append(Line2D([], [], color=colours[index], marker=markers[index],
                                  linestyle='-', markersize=6, label=label))
        handles.append(Line2D([], [], color=NEUTRAL, marker='o', linestyle='none',
                              markerfacecolor='none', markersize=6,
                              label='outside the largest piece'))

        value = float(np.mean(list(panel['share_of_group'].values())))
        connectivity[panel['feature']] = value
        axis.set_title(f"{panel['feature']}\ngraph connectivity = {value:.2f}   "
                       f"({k} nearest neighbours)", color=INK, fontsize=12, pad=12)
        axis.set_facecolor('white')
        for side in ('top', 'right', 'bottom', 'left'):
            axis.spines[side].set_visible(False)
        axis.set_xticks([])
        axis.set_yticks([])
        axis.set_aspect('equal', adjustable='datalim')
        axis.autoscale_view()
        axis.margins(0.06)
        if len(handles) <= 9:
            axis.legend(handles=handles, loc='best', frameon=False, fontsize=8,
                        labelcolor=INK_SECONDARY)
        else:
            axis.set_xlabel(f"{len(groups)} groups - too many to list, see the table",
                            color=INK_SECONDARY, fontsize=9)

    figure.tight_layout()
    figure.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)))
    plt.close(figure)
    return connectivity

def _alignment_score_from_distance(distance_matrix, labels, k):
    import numpy as np
    label_values = np.asarray(labels)
    groups, group_sizes = np.unique(label_values, return_counts=True)
    if len(groups) < 2:
        return None
    neighbours = _knn_indices_from_distance(distance_matrix, k)
    if neighbours is None:
        return None
    from_other_group = [
        float(np.mean(label_values[neighbours[sample]] != label_values[sample]))
        for sample in range(len(label_values))
    ]
    return float(np.mean(from_other_group))

def alignment_score_expected(labels):
    import numpy as np
    label_values = np.asarray(labels)
    _, group_sizes = np.unique(label_values, return_counts=True)
    if len(group_sizes) < 2:
        return None
    shares = group_sizes / group_sizes.sum()
    return float(1.0 - np.sum(shares ** 2))

def _entropy_score_from_distance(distance_matrix, labels, k):
    import numpy as np
    label_values = np.asarray(labels)
    groups = np.unique(label_values)
    if len(groups) < 2:
        return None
    neighbours = _knn_indices_from_distance(distance_matrix, k)
    if neighbours is None:
        return None

    maximum_entropy = np.log(len(groups))
    entropies = []
    for sample in range(len(label_values)):
        neighbour_labels = label_values[neighbours[sample]]
        shares = np.array([(neighbour_labels == group).mean() for group in groups])
        shares = shares[shares > 0]
        entropies.append(float(-np.sum(shares * np.log(shares)) / maximum_entropy))
    return float(np.mean(entropies))

def _neighbourhood_metrics_from_distance(distance_matrix, labels):
    import glb
    k = int(getattr(glb, 'neighbourhood_k', 30))
    metrics = {'kBET': None, 'LISI': None, 'graph-connectivity': None,
               'alignment-score': None, 'alignment-score-max': None, 'entropy-score': None}
    for name, calculate in (('kBET', _kbet_from_distance),
                            ('LISI', _lisi_from_distance),
                            ('graph-connectivity', _graph_connectivity_from_distance),
                            ('alignment-score', _alignment_score_from_distance),
                            ('entropy-score', _entropy_score_from_distance)):
        try:
            metrics[name] = calculate(distance_matrix, labels, k)
        except Exception as e:
            print(f"{name} could not be calculated: {e}")
    try:
        metrics['alignment-score-max'] = alignment_score_expected(labels)
    except Exception as e:
        print(f"alignment-score-max could not be calculated: {e}")
    return metrics

def lisi_name(covariate, study_name, factor_of_interest):
    if covariate == study_name:
        return 'iLISI'
    if covariate == factor_of_interest:
        return 'cLISI'
    return 'LISI'

def dataset_key(name):
    name = str(name).replace("clean-", "").replace("csv", "").replace("tsv", "")
    return name.rstrip(".")

def _roc_points(y_true, probabilities, classes):
    from sklearn.metrics import roc_curve
    import numpy as np
    binary, scores = [], []
    for position, group in enumerate(classes):
        belongs_to_group = (y_true == group).astype(int)
        if belongs_to_group.sum() in (0, len(belongs_to_group)):
            continue
        binary.append(belongs_to_group)
        scores.append(probabilities[:, position])
    if not binary:
        return None
    false_positive_rate, true_positive_rate, _ = roc_curve(np.concatenate(binary), np.concatenate(scores))
    return false_positive_rate.tolist(), true_positive_rate.tolist()

def roc_plot(dataset_name, best_method, output, date):
    import matplotlib.pyplot as plt
    import glb

    curves = getattr(glb, 'roc_curves', {})
    raw = curves.get((dataset_name, 'uncorrected'))
    corrected = curves.get((dataset_name, best_method))
    if raw is None and corrected is None:
        print(f"No ROC curves were stored for {dataset_name}, the plot is skipped.")
        return None

    fig, axs = plt.subplots(1, 2, figsize=(14, 6))
    schemes = [('cv', 'Cross validation'), ('lobo', 'Leave one batch out')]
    for ax, (scheme, scheme_title) in zip(axs, schemes):
        for label, stored, colour in [("uncorrected", raw, ROLE_COLOURS['uncorrected']),
                                      (f"corrected ({best_method})", corrected, ROLE_COLOURS['phenotype'])]:
            if not stored:
                continue
            points = stored.get(scheme)
            auroc = stored.get(f"{scheme}-auroc")
            if not points:
                continue
            legend = f"{label} (AUROC {auroc:.3f})" if auroc is not None else label
            ax.plot(points[0], points[1], color=colour, linewidth=2, label=legend)
        ax.plot([0, 1], [0, 1], linestyle="--", color="black", linewidth=1, label="random (AUROC 0.500)")
        ax.set_xlabel("False positive rate")
        ax.set_ylabel("True positive rate")
        ax.set_title(scheme_title)
        ax.set_xlim(-0.02, 1.02)
        ax.set_ylim(-0.02, 1.02)
        ax.legend(loc="lower right")
    fig.suptitle(f"Prediction of the factor of interest before and after correction: {dataset_name}", fontsize=14)
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    file_name = f"{output}/report/ROC-{dataset_name}-{date}.png"
    plt.savefig(file_name, dpi=int(setting('figure_dpi', 300)))
    plt.close(fig)
    return file_name

def _auroc_from_predictions(y_true, probabilities, classes):
    from sklearn.metrics import roc_auc_score
    import numpy as np
    scores = []
    for position, group in enumerate(classes):
        belongs_to_group = (y_true == group).astype(int)
        if belongs_to_group.sum() in (0, len(belongs_to_group)):
            continue
        scores.append(roc_auc_score(belongs_to_group, probabilities[:, position]))
    return float(np.mean(scores)) if scores else None

def design_balance(df, study_name, factor_of_interest):
    import numpy as np
    import pandas as pd
    from scipy.stats import chi2_contingency

    if study_name not in df.columns or factor_of_interest not in df.columns:
        return None
    table = pd.crosstab(df[study_name].astype(str), df[factor_of_interest].astype(str))
    if table.shape[0] < 2 or table.shape[1] < 2:
        return None
    try:
        chi_squared, p_value, _, _ = chi2_contingency(table)
    except Exception as e:
        print(f"Design balance could not be calculated: {e}")
        return None

    n = table.to_numpy().sum()
    smaller_dimension = min(table.shape) - 1
    cramers_v = float(np.sqrt(chi_squared / (n * smaller_dimension))) if smaller_dimension > 0 else None

    if cramers_v is None:
        verdict = "not available"
    elif cramers_v < 0.1:
        verdict = "balanced - batch and phenotype are essentially independent"
    elif cramers_v < 0.3:
        verdict = "weak association - correction is safe"
    elif cramers_v < 0.5:
        verdict = "moderate association - interpret the corrected data with care"
    else:
        verdict = "STRONG association - the correction will remove part of the biology as well"
    return {'p-value': float(p_value), 'cramers-v': cramers_v, 'verdict': verdict,
            'table': table, 'counts': table.to_json(orient='split')}

def variance_partitioning(df, study_name, factor_of_interest):
    import numpy as np
    import pandas as pd

    prepared = _prepare_for_distance_tests(df, study_name)
    if prepared is None:
        return None
    distance_matrix, _, batch_labels = prepared
    phenotype_prepared = _prepare_for_distance_tests(df, factor_of_interest)
    if phenotype_prepared is None:
        return None
    _, _, phenotype_labels = phenotype_prepared
    if len(batch_labels) != len(phenotype_labels):
        print("Variance partitioning skipped: batch and phenotype cover different samples.")
        return None

    def r_squared(labels):
        label_values = np.asarray(labels)
        ss_total = np.sum(distance_matrix ** 2) / distance_matrix.shape[0]
        ss_within = 0.0
        for group in np.unique(label_values):
            group_index = np.where(label_values == group)[0]
            if len(group_index) > 1:
                group_distances = distance_matrix[np.ix_(group_index, group_index)]
                ss_within += np.sum(group_distances ** 2) / len(group_index)
        return float((ss_total - ss_within) / ss_total) if ss_total > 0 else 0.0

    combined = pd.Series([f"{b}|{p}" for b, p in zip(np.asarray(batch_labels),
                                                     np.asarray(phenotype_labels))])
    r2_batch, r2_phenotype, r2_both = r_squared(batch_labels), r_squared(phenotype_labels), r_squared(combined)

    shared = r2_batch + r2_phenotype - r2_both
    return {
        'batch-only': float(max(0.0, r2_both - r2_phenotype)),
        'phenotype-only': float(max(0.0, r2_both - r2_batch)),
        'shared': float(shared),
        'unexplained': float(max(0.0, 1.0 - r2_both)),
    }

def pvca(df, study_name, factor_of_interest, variance_threshold=None, max_components=None):
    import numpy as np
    import pandas as pd
    from sklearn.decomposition import PCA as SklearnPCA

    if variance_threshold is None:
        variance_threshold = float(setting('pvca_variance_threshold', 0.8))
    if max_components is None:
        max_components = int(setting('pvca_max_components', 10))

    if study_name not in df.columns or factor_of_interest not in df.columns:
        return None
    data = df.dropna(subset=[study_name, factor_of_interest])
    batch = data[study_name].astype(str).to_numpy()
    phenotype = data[factor_of_interest].astype(str).to_numpy()
    if len(np.unique(batch)) < 2:
        return None

    features = _feature_matrix(data)
    if features is None or features.shape[1] < 2 or features.shape[0] < 4:
        return None

    n_components = int(min(max_components, features.shape[0] - 1, features.shape[1]))
    if n_components < 1:
        return None
    pca = SklearnPCA(n_components=n_components, random_state=seed())
    scores = pca.fit_transform(features)
    explained = pca.explained_variance_ratio_
    keep = int(np.searchsorted(np.cumsum(explained), variance_threshold) + 1)
    keep = max(1, min(keep, n_components))
    scores, explained = scores[:, :keep], explained[:keep]
    weights = explained / explained.sum()

    interaction = np.array([f"{b}|{p}" for b, p in zip(batch, phenotype)])

    def explained_share(values, labels):
        overall_mean = values.mean()
        total = float(np.sum((values - overall_mean) ** 2))
        if total <= 0:
            return 0.0
        between = 0.0
        for group in np.unique(labels):
            in_group = values[labels == group]
            between += len(in_group) * (in_group.mean() - overall_mean) ** 2
        return float(min(1.0, between / total))

    components = {'batch': 0.0, 'phenotype': 0.0, 'interaction': 0.0, 'residual': 0.0}
    for direction in range(scores.shape[1]):
        values = scores[:, direction]
        share_batch = explained_share(values, batch)
        share_phenotype = explained_share(values, phenotype)
        share_both = explained_share(values, interaction)
        share_interaction = max(0.0, share_both - share_batch - share_phenotype)
        residual = max(0.0, 1.0 - share_batch - share_phenotype - share_interaction)
        components['batch'] += weights[direction] * share_batch
        components['phenotype'] += weights[direction] * share_phenotype
        components['interaction'] += weights[direction] * share_interaction
        components['residual'] += weights[direction] * residual

    total = sum(components.values())
    if total <= 0:
        return None
    return {name: float(100.0 * value / total) for name, value in components.items()}

def feature_association(df, covariate):
    import numpy as np
    from scipy.stats import kruskal
    from statsmodels.stats.multitest import multipletests

    if covariate not in df.columns:
        return None
    data = df.dropna(subset=[covariate])
    labels = data[covariate].astype(str).to_numpy()
    groups = np.unique(labels)
    if len(groups) < 2:
        return None
    features = _feature_matrix(data, standardise=False)
    if features is None or features.shape[1] == 0:
        return None

    p_values = []
    for column in range(features.shape[1]):
        values = features[:, column]
        if np.all(values == values[0]):
            continue
        samples_per_group = [values[labels == group] for group in groups]
        if any(len(group_values) < 2 for group_values in samples_per_group):
            continue
        try:
            p_values.append(kruskal(*samples_per_group).pvalue)
        except Exception:
            continue
    if not p_values:
        return None

    significant = multipletests(p_values, alpha=float(setting('significance_alpha', 0.05)),
                                method='fdr_bh')[0]
    return float(100.0 * significant.sum() / len(p_values))

def _feature_matrix(df, standardise=True):
    import json
    import numpy as np
    import pandas as pd
    import glb

    raw_data_folder = glb.raw_data_folder
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    to_drop = [str(config["study_name"]), str(config["factor_of_interest"]), str(config["sample_id_column"])]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
        to_drop.extend(line.strip() for line in covariate_file)

    features = df.copy()
    features.columns = features.columns.astype(str)
    features = features.drop(columns=[col for col in to_drop if col in features.columns])
    features = features.apply(pd.to_numeric, errors='coerce').fillna(0.0)
    if features.shape[1] == 0:
        return None
    values = features.to_numpy(dtype=float)
    if standardise:
        spread = values.std(axis=0)
        values = values[:, spread > 0]
        spread = spread[spread > 0]
        if values.shape[1] == 0:
            return None
        values = (values - values.mean(axis=0)) / spread
    return values

def classification_auroc(df, dataset_name=None, method=None):
    import numpy as np
    import pandas as pd
    import json
    import glb
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold

    empty = {'cv': None, 'lobo': None}
    if not getattr(glb, 'run_auroc', True):
        return empty

    stored_curves = {}
    def store(scheme, points, auroc):
        stored_curves[scheme] = points
        stored_curves[f"{scheme}-auroc"] = auroc

    raw_data_folder = glb.raw_data_folder
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])
    sample_id_column = str(config["sample_id_column"])

    data = df.copy()
    data.columns = data.columns.astype(str)
    if factor_of_interest not in data.columns or study_name not in data.columns:
        print("AUROC: batch or factor of interest column is missing, skipping.")
        return empty

    data = data.dropna(subset=[factor_of_interest, study_name])

    to_drop = [study_name, factor_of_interest, sample_id_column]
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
        to_drop.extend(line.strip() for line in covariate_file)

    y = data[factor_of_interest].astype(str).values
    batches = data[study_name].astype(str).values
    X = data.drop(columns=[col for col in to_drop if col in data.columns])
    X = X.apply(pd.to_numeric, errors='coerce').fillna(0.0).values

    classes = np.unique(y)
    if len(classes) < 2 or X.shape[1] == 0:
        print("AUROC: fewer than two phenotype groups or no features, skipping.")
        return empty

    def new_classifier():
        return RandomForestClassifier(n_estimators=int(setting('auroc_trees', 200)),
                                     random_state=seed(), n_jobs=-1)

    def probabilities_in_global_order(classifier, X_test):
        aligned = np.zeros((X_test.shape[0], len(classes)))
        proba = classifier.predict_proba(X_test)
        for position, group in enumerate(classifier.classes_):
            aligned[:, list(classes).index(group)] = proba[:, position]
        return aligned

    cv_auroc = None
    smallest_group = int(pd.Series(y).value_counts().min())
    n_splits = min(int(setting('auroc_folds', 5)), smallest_group)
    if n_splits >= 2:
        try:
            out_of_fold = np.zeros((len(y), len(classes)))
            folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed())
            for train_index, test_index in folds.split(X, y):
                classifier = new_classifier()
                classifier.fit(X[train_index], y[train_index])
                out_of_fold[test_index] = probabilities_in_global_order(classifier, X[test_index])
            cv_auroc = _auroc_from_predictions(y, out_of_fold, classes)
            store('cv', _roc_points(y, out_of_fold, classes), cv_auroc)
        except Exception as e:
            print(f"AUROC (cross validation) could not be calculated: {e}")
    else:
        print(f"AUROC (cross validation): the smallest phenotype group has {smallest_group} sample(s), skipping.")

    lobo_auroc = None
    unique_batches = np.unique(batches)
    if len(unique_batches) >= 2:
        try:
            scores = []
            pooled_true, pooled_probabilities = [], []
            for batch in unique_batches:
                test_index = np.where(batches == batch)[0]
                train_index = np.where(batches != batch)[0]
                if len(np.unique(y[test_index])) < 2 or len(np.unique(y[train_index])) < 2:
                    continue
                classifier = new_classifier()
                classifier.fit(X[train_index], y[train_index])
                fold_probabilities = probabilities_in_global_order(classifier, X[test_index])
                score = _auroc_from_predictions(y[test_index], fold_probabilities, classes)
                if score is not None:
                    scores.append(score)
                    pooled_true.append(y[test_index])
                    pooled_probabilities.append(fold_probabilities)
            if scores:
                lobo_auroc = float(np.mean(scores))
                store('lobo', _roc_points(np.concatenate(pooled_true),
                                          np.concatenate(pooled_probabilities), classes), lobo_auroc)
                print(f"AUROC (leave one batch out): {lobo_auroc:.3f}, averaged over {len(scores)} of {len(unique_batches)} batches")
            else:
                print("AUROC (leave one batch out): no batch holds more than one phenotype group, skipping.")
        except Exception as e:
            print(f"AUROC (leave one batch out) could not be calculated: {e}")

    if dataset_name is not None and stored_curves:
        if not hasattr(glb, 'roc_curves') or glb.roc_curves is None:
            glb.roc_curves = {}
        glb.roc_curves[(dataset_key(dataset_name), method)] = stored_curves

    return {'cv': cv_auroc, 'lobo': lobo_auroc}

def permanova(df, feature):
    prepared = _prepare_for_distance_tests(df, feature)
    if prepared is None:
        return None
    distance_matrix, distance_matrix_object, labels = prepared
    return _permanova_from_distance(distance_matrix, distance_matrix_object, labels)

def permdisp(df, feature):
    prepared = _prepare_for_distance_tests(df, feature)
    if prepared is None:
        return None
    distance_matrix, distance_matrix_object, labels = prepared
    return _permdisp_from_distance(distance_matrix_object, labels)

def distance_based_metrics(df, feature):
    import glb
    prepared = _prepare_for_distance_tests(df, feature)
    if prepared is None:
        return None
    distance_matrix, distance_matrix_object, labels = prepared
    pValue, FStatistics, R2 = _permanova_from_distance(distance_matrix, distance_matrix_object, labels)
    metrics = {
        'permanova-p-value': pValue,
        'permanova-F-value': FStatistics,
        'permanova-R2': R2,
        'permdisp-p-value': None,
        'permdisp-F-value': None,
        'silhouette': _silhouette_from_distance(distance_matrix, labels),
        'kBET': None,
        'LISI': None,
        'graph-connectivity': None,
        'alignment-score': None,
        'alignment-score-max': None,
        'entropy-score': None,
    }
    if getattr(glb, 'run_permdisp', True):
        metrics['permdisp-p-value'], metrics['permdisp-F-value'] = _permdisp_from_distance(distance_matrix_object, labels)
    if getattr(glb, 'run_neighbourhood_metrics', True):
        metrics.update(_neighbourhood_metrics_from_distance(distance_matrix, labels))
    return metrics

def permanova_permdisp(df, feature):
    metrics = distance_based_metrics(df, feature)
    if metrics is None:
        return None
    return (metrics['permanova-p-value'], metrics['permanova-F-value'], metrics['permanova-R2'],
            metrics['permdisp-p-value'], metrics['permdisp-F-value'], metrics['silhouette'])

def dispersion_confounded(permanova_p, permdisp_p, alpha=None):
    if alpha is None:
        alpha = float(setting('significance_alpha', 0.05))
    try:
        return float(permanova_p) < alpha and float(permdisp_p) < alpha
    except (TypeError, ValueError):
        return False

def data_cleaning(dataset: pd.DataFrame, threshold: float) -> pd.DataFrame:
    #import numpy as np
    import pandas as pd
    #Transpose so that features are rows
    dataset_T = dataset.transpose(copy=True)
    #Load metadata (covariates to exclude from NaN-cleaning)
    bernard_folder = glb.bernard_folder
    raw_data_folder = f"{bernard_folder}/raw-data"
    with open(f"{raw_data_folder}/covariates.txt", "r") as f:
        metadata = set(line.strip() for line in f)
    #Force numeric dtype everywhere (OS-stable)
    dataset_T = dataset_T.apply(pd.to_numeric, errors="coerce")
    non_metadata_rows = dataset_T.index.difference(metadata)
    dataset_T.loc[non_metadata_rows] = (
        dataset_T.loc[non_metadata_rows]
        .fillna(0.0)
        .clip(lower=0.0)
    )
    #Drop features with too many zeros
    zero_ratio = (dataset_T == 0.0).mean(axis=1)
    dataset_T = dataset_T.loc[zero_ratio <= threshold]
    # 6. Drop features that are entirely zero
    dataset_T = dataset_T.loc[(dataset_T != 0.0).any(axis=1)]
    #Transpose back so features are columns again
    return dataset_T.transpose(copy=True)

def samples_selection(df, threshold):
    print(f"Samples with more than {threshold*100} percentage of zero values will be removed.\n")
    # Calculate the percentage of zeros in each row
    zero_percentage = (df == 0).mean(axis=1)
    # Filter out rows with more than 90% of zeros
    df = df[zero_percentage < threshold]
    print("Sparse samples have been removed.")
    return df

def table_for_dimensionality_reduction_variables(df):
    bernard_folder = glb.bernard_folder
    raw_data_folder = bernard_folder + "/raw-data"
    import json
    # Define what are names of sample ID, study ID and phenotype columns in config.json file
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])
    columns_to_exclude = [study_name, factor_of_interest] #from config.json file
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            metadata = [line.strip() for line in covariate_file] #metadata from covariates.txt file
    columns_to_exclude.extend(metadata) #columns to exclude now contains all metadata from covariates.txt file together with batch and factor of interest
    columns_to_exclude = [col for col in columns_to_exclude] #creates a new list that contains all elements from columns_to_exclude
    dimensionality_reduction = df.copy()
    dimensionality_reduction.drop(columns=[col for col in columns_to_exclude if col in dimensionality_reduction.columns],
                                  inplace=True,
                                  errors='raise') #drops all columns from columns:to_exclude list
    dimensionality_reduction = dimensionality_reduction.apply(pd.to_numeric, errors='coerce') # only columns with numeric values can go through dimensionality reduction algorithms
    dimensionality_reduction = dimensionality_reduction.dropna(axis=1, how='all')
    dimensionality_reduction.columns = dimensionality_reduction.columns.astype(str) #convert all column names to strings (some libraries expect string column names for safety and consistency)
    dimensionality_reduction = dimensionality_reduction.fillna(0)
    from sklearn.preprocessing import StandardScaler 
    variables = dimensionality_reduction #ensures that each variable contributes equally to the analysis
    variables = StandardScaler().fit_transform(variables)
    return variables

def table_for_dimensionality_reduction(df, feature):
    bernard_folder = glb.bernard_folder
    raw_data_folder = bernard_folder + "/raw-data"
    import json
    # Define what are names of sample ID, study ID and phenotype columns in config.json file
    with open(f"{raw_data_folder}/config.json", "r") as config_file:
        config = json.load(config_file)
    study_name = str(config["study_name"])
    factor_of_interest = str(config["factor_of_interest"])

    dimensionality_reduction = df.copy()
    dimensionality_reduction.reset_index(inplace = True)
    columns_to_exclude = [study_name, factor_of_interest] #from config.json file
    with open(f"{raw_data_folder}/covariates.txt", "r") as covariate_file:
            metadata = [line.strip() for line in covariate_file] #metadata from covariates.txt file
    columns_to_exclude.extend(metadata) #columns to exclude now contains all metadata from covariates.txt file together with batch and factor of interest
    columns_to_exclude = [col for col in columns_to_exclude if col != feature] #creates a new list that contains all elements from columns_to_exclude, except the one that equals feature
    dimensionality_reduction.drop(columns=[col for col in columns_to_exclude if col in dimensionality_reduction.columns], 
                                  inplace=True, 
                                  errors='raise') #drops all columns from columns:to_exclude list
    target_featrue = dimensionality_reduction[feature].to_frame() #this is dataframe with column feature only (a dataframe with one column)
    return target_featrue

def PCA(variables, target_bioProject, target_diagnosis, title, file_name, features_list, output):
    from sklearn.decomposition import PCA
    import seaborn as sns
    import pandas as pd
    import matplotlib.pyplot as plt
    pca = PCA(n_components=2, random_state=seed())  #reduce to 2 dimensions
    principalComponents = pca.fit_transform(variables) #performs PCA on variables (only numeric data without metadata)
    X_reduced_PCA = pd.DataFrame(data=principalComponents, columns=['PCA1', 'PCA2']) #PCA results are stored as pandas data frame
    X_reduced_PCA = pd.concat([X_reduced_PCA, target_bioProject, target_diagnosis], axis=1)
    share = 100 * pca.explained_variance_ratio_[:2]
    _scatter_by_group(X_reduced_PCA, 'PCA1', 'PCA2', features_list, None,
                      title, f'PCA1 ({share[0]:.1f}%)', f'PCA2 ({share[1]:.1f}%)',
                      f"{output}/report/PCA-{file_name}.png")

def MDS(variables, target_bioProject, target_diagnosis, title, file_name, features_list, output):
    from sklearn.manifold import MDS
    import seaborn as sns
    import pandas as pd
    import matplotlib.pyplot as plt
    mds = MDS(n_components=2, random_state=seed())  #reduce to 2 dimensions
    principalComponents = mds.fit_transform(variables) #performs MDS on variables (only numeric data without metadata)
    X_reduced_MDS = pd.DataFrame(data=principalComponents, columns=['MDS1', 'MDS2']) #MDS results are stored as pandas data frame
    X_reduced_MDS = pd.concat([X_reduced_MDS, target_bioProject, target_diagnosis], axis=1)
    _scatter_by_group(X_reduced_MDS, 'MDS1', 'MDS2', features_list, None,
                      title, 'MDS1', 'MDS2',
                      f"{output}/report/MDS-{file_name}.png")

def TSNE(variables, target_bioProject, target_diagnosis, title, file_name, features_list, output):
    from sklearn.manifold import TSNE
    import seaborn as sns
    import pandas as pd
    import matplotlib.pyplot as plt
    n_samples = len(variables)
    chosen_perplexity = float(setting('tsne_perplexity', 0.0))
    if chosen_perplexity > 0:
        perplexity = chosen_perplexity
    else:
        perplexity = max(2.0, min(30.0, (n_samples - 1) / 3.0))
    if perplexity >= n_samples:
        perplexity = max(1.0, n_samples - 1.0)
    tsne = TSNE(n_components=2, perplexity=perplexity, random_state=seed())  #reduce to 2 dimensions
    principalComponents = tsne.fit_transform(variables) #performs TSNE on variables (only numeric data without metadata)
    X_reduced_TSNE = pd.DataFrame(data=principalComponents, columns=['TSNE1', 'TSNE2']) #TSNE results are stored as pandas data frame
    X_reduced_TSNE = pd.concat([X_reduced_TSNE, target_bioProject, target_diagnosis], axis=1)
    _scatter_by_group(X_reduced_TSNE, 'TSNE1', 'TSNE2', features_list, None,
                      title, 'TSNE1', 'TSNE2',
                      f"{output}/report/TSNE-{file_name}.png")

def PCoA(df, target_bioProject, target_diagnosis, title, file_name, features_list, output,
         distance="aitchison"):
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from scipy.spatial.distance import pdist, squareform
    import glb

    previous_space = getattr(glb, 'evaluation_space', 'zscore-euclidean')
    glb.evaluation_space = distance
    try:
        prepared = _prepare_for_distance_tests(df, features_list[0])
    finally:
        glb.evaluation_space = previous_space
    if prepared is None:
        return None
    distance_matrix, _, _ = prepared

    n = distance_matrix.shape[0]
    squared = distance_matrix ** 2
    centring = np.eye(n) - np.ones((n, n)) / n
    centred = -0.5 * centring.dot(squared).dot(centring)
    eigenvalues, eigenvectors = np.linalg.eigh(centred)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    positive = eigenvalues > 0
    if positive.sum() < 2:
        print("PCoA needs at least two positive eigenvalues, skipping.")
        return None
    coordinates = eigenvectors[:, :2] * np.sqrt(eigenvalues[:2])
    share = 100 * eigenvalues[:2] / eigenvalues[positive].sum()

    coordinates = pd.DataFrame(coordinates, columns=['PCo1', 'PCo2'])
    plot_data = pd.concat([coordinates, target_bioProject.reset_index(drop=True),
                           target_diagnosis.reset_index(drop=True)], axis=1)
    _scatter_by_group(plot_data, 'PCo1', 'PCo2', features_list, plot_data.columns[0],
                      f"{title}", f"PCo1 ({share[0]:.1f}%)", f"PCo2 ({share[1]:.1f}%)",
                      f"{output}/report/PCoA-{file_name}.png")
    return share

def _scatter_by_group(plot_data, x, y, features_list, _unused, title, xlabel, ylabel, path):
    import matplotlib.pyplot as plt
    import numpy as np
    from scipy.stats import gaussian_kde

    n_panels = len(features_list)
    fig = plt.figure(figsize=(7.0 * n_panels, 6.4))
    fig.suptitle(title, fontsize=15, color=INK, y=0.99)
    panels = fig.subfigures(1, n_panels) if n_panels > 1 else [fig.subfigures(1, 1)]

    for panel, feature in zip(panels, features_list):
        grid = panel.add_gridspec(2, 2, width_ratios=(5, 1), height_ratios=(1, 5),
                                  wspace=0.04, hspace=0.04)
        ax = panel.add_subplot(grid[1, 0])
        ax_top = panel.add_subplot(grid[0, 0], sharex=ax)
        ax_right = panel.add_subplot(grid[1, 1], sharey=ax)

        groups = list(pd.unique(plot_data[feature].astype(str)))
        colours, markers = group_colours(len(groups)), group_markers(len(groups))
        for i, group in enumerate(groups):
            rows = plot_data[plot_data[feature].astype(str) == group]
            ax.scatter(rows[x], rows[y], s=40, c=colours[i], marker=markers[i],
                       edgecolors='white', linewidths=0.6, alpha=0.9, label=str(group), zorder=3)
            for axis, values, vertical in ((ax_top, rows[x].to_numpy(), False),
                                           (ax_right, rows[y].to_numpy(), True)):
                values = values[np.isfinite(values)]
                if len(values) < 3 or np.std(values) <= 0:
                    continue
                try:
                    density = gaussian_kde(values)
                except Exception:
                    continue
                span = np.linspace(values.min(), values.max(), 200)
                curve = density(span)
                if vertical:
                    axis.plot(curve, span, color=colours[i], linewidth=1.6)
                    axis.fill_betweenx(span, 0, curve, color=colours[i], alpha=0.18)
                else:
                    axis.plot(span, curve, color=colours[i], linewidth=1.6)
                    axis.fill_between(span, 0, curve, color=colours[i], alpha=0.18)

        style_axes(ax, title=None, xlabel=xlabel, ylabel=ylabel)
        ax.grid(True, axis='both', color=GRID, linewidth=0.8, zorder=0)
        for axis in (ax_top, ax_right):
            axis.set_facecolor('white')
            for side in ('top', 'right', 'left', 'bottom'):
                axis.spines[side].set_visible(False)
            axis.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax_top.set_title(str(feature), color=INK, fontsize=12, pad=8)

        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, labels, title=str(feature), loc='upper center',
                  bbox_to_anchor=(0.5, -0.14), ncol=min(4, max(1, len(groups))),
                  frameon=False, fontsize=8, title_fontsize=9)

    plt.savefig(path, dpi=int(setting('figure_dpi', 300)), facecolor='white', bbox_inches='tight')
    plt.close(fig)

def batch_dissimilarity_summary(records, output, title):
    import matplotlib.pyplot as plt
    if not records:
        return None
    records = sorted(records, key=lambda r: r['excess'])
    labels = [r['method'] for r in records]
    values = [r['excess'] for r in records]
    colours = [ROLE_COLOURS['uncorrected'] if m == 'uncorrected' else ROLE_COLOURS['batch']
               for m in labels]

    fig, ax = plt.subplots(figsize=(max(9.0, len(labels) * 0.85), 5.0))
    bars = ax.bar(labels, values, color=colours, width=0.68, zorder=3)
    for bar, value in zip(bars, values):
        ax.annotate(f"{value:.3f}", (bar.get_x() + bar.get_width() / 2, value),
                    ha='center', va='bottom' if value >= 0 else 'top',
                    fontsize=8, color=INK_SECONDARY, xytext=(0, 3), textcoords='offset points')
    ax.axhline(0, color=INK_SECONDARY, linewidth=1)
    style_axes(ax, title=None,
               xlabel="", ylabel="between-batch minus within-batch dissimilarity")
    ax.set_title("Leftover batch separation after correction (lower is better)",
                 color=INK, fontsize=13, pad=14)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)), facecolor='white')
    plt.close(fig)
    return records

def mean_between_group_excess(df, feature):
    import numpy as np
    import glb
    previous_space = getattr(glb, 'evaluation_space', 'zscore-euclidean')
    glb.evaluation_space = 'braycurtis'
    try:
        prepared = _prepare_for_distance_tests(df, feature)
    finally:
        glb.evaluation_space = previous_space
    if prepared is None:
        return None
    distance_matrix, _, labels = prepared
    label_values = np.asarray(labels)
    if len(np.unique(label_values)) < 2:
        return None
    same = label_values[:, None] == label_values[None, :]
    upper = np.triu(np.ones_like(distance_matrix, dtype=bool), k=1)
    within = distance_matrix[same & upper]
    between = distance_matrix[(~same) & upper]
    if within.size == 0 or between.size == 0:
        return None
    return float(between.mean() - within.mean())

def feature_r2(df, covariate):
    import numpy as np
    if covariate not in df.columns:
        return None
    data = df.dropna(subset=[covariate])
    labels = data[covariate].astype(str).to_numpy()
    groups = np.unique(labels)
    if len(groups) < 2:
        return None
    features = _feature_matrix(data, standardise=False)
    if features is None or features.shape[1] == 0:
        return None

    values = []
    overall_mean = features.mean(axis=0)
    total = ((features - overall_mean) ** 2).sum(axis=0)
    between = np.zeros(features.shape[1])
    for group in groups:
        in_group = features[labels == group]
        if len(in_group) == 0:
            continue
        between += len(in_group) * (in_group.mean(axis=0) - overall_mean) ** 2
    usable = total > 0
    values = between[usable] / total[usable]
    return np.clip(values, 0.0, 1.0)

def feature_r2_plot(distributions, output, title, factor_of_interest, study_name):
    import matplotlib.pyplot as plt
    import numpy as np
    if not distributions:
        return None
    methods = [d['method'] for d in distributions]
    fig, ax = plt.subplots(figsize=(max(9.0, len(methods) * 1.0), 5.0))
    positions, tick_positions = [], []
    for i, entry in enumerate(distributions):
        base = i * 2.4
        tick_positions.append(base + 0.5)
        for offset, key, role in ((0.0, 'batch', 'batch'), (1.0, 'phenotype', 'phenotype')):
            values = entry.get(key)
            if values is None or len(values) == 0:
                continue
            box = ax.boxplot([values], positions=[base + offset], widths=0.62, patch_artist=True,
                             showfliers=False, zorder=3)
            for patch in box['boxes']:
                patch.set_facecolor(ROLE_COLOURS[role]); patch.set_alpha(0.85)
                patch.set_edgecolor('white'); patch.set_linewidth(1.2)
            for element in ('whiskers', 'caps', 'medians'):
                for line in box[element]:
                    line.set_color(INK_SECONDARY); line.set_linewidth(1.0)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(methods, rotation=45, ha='right')
    style_axes(ax, title=None, xlabel="", ylabel="R2 of a single feature")
    ax.set_title(f"How much of each feature is explained by {study_name} and by {factor_of_interest}\n"
                 f"(the {study_name} boxes should collapse, the {factor_of_interest} boxes should not)",
                 color=INK, fontsize=12, pad=14)
    handles = [plt.Rectangle((0, 0), 1, 1, facecolor=ROLE_COLOURS['batch'], alpha=0.85),
               plt.Rectangle((0, 0), 1, 1, facecolor=ROLE_COLOURS['phenotype'], alpha=0.85)]
    legend = ax.legend(handles, [study_name, factor_of_interest], loc='upper center',
                       bbox_to_anchor=(0.5, -0.22), ncol=2, frameon=False, fontsize=9)
    plt.tight_layout(rect=[0, 0.02, 1, 1])
    plt.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)), facecolor='white')
    plt.close(fig)
    return True

def variance_partition_plot(records, output, title):
    import matplotlib.pyplot as plt
    import numpy as np
    if not records:
        return None
    methods = [r['method'] for r in records]
    pieces = [('phenotype-only', 'phenotype'), ('batch-only', 'batch'),
              ('shared', 'shared'), ('unexplained', 'residual')]
    clamped = np.array([[max(0.0, float(r.get(key) or 0.0)) for key, _ in pieces] for r in records])
    totals = clamped.sum(axis=1)
    totals[totals <= 0] = 1.0
    clamped = clamped / totals[:, None]

    bottom = np.zeros(len(records))
    fig, ax = plt.subplots(figsize=(max(9.0, len(methods) * 0.9), 5.0))
    for column, (key, role) in enumerate(pieces):
        values = clamped[:, column]
        ax.bar(methods, values, bottom=bottom, color=ROLE_COLOURS[role], width=0.7,
               edgecolor='white', linewidth=2, zorder=3, label=key.replace('-', ' '))
        bottom += values
    ax.set_ylim(0, 1.0)
    style_axes(ax, title=None, xlabel="", ylabel="share of the total variability")
    ax.set_title("Where the variability comes from, before and after correction",
                 color=INK, fontsize=13, pad=14)
    plt.xticks(rotation=45, ha='right')
    legend = ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=4,
                       frameon=False, fontsize=9)
    plt.tight_layout(rect=[0, 0.02, 1, 1])
    plt.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)), facecolor='white')
    plt.close(fig)
    return True

def NMDS(variables, target_bioProject, target_diagnosis, title, file_name, features_list, output):
    from sklearn.manifold import MDS as SklearnMDS
    import seaborn as sns
    import pandas as pd
    import matplotlib.pyplot as plt
    import numpy as np
    nmds = SklearnMDS(n_components=2, metric=False, random_state=seed(),
                      normalized_stress=True, n_init=4, max_iter=300)
    coordinates = nmds.fit_transform(variables)
    stress = float(getattr(nmds, 'stress_', float('nan')))
    quality = ("excellent" if stress < 0.05 else "good" if stress < 0.1
               else "usable" if stress < 0.2 else "not trustworthy")
    X_reduced = pd.DataFrame(data=coordinates, columns=['NMDS1', 'NMDS2'])
    X_reduced = pd.concat([X_reduced, target_bioProject, target_diagnosis], axis=1)
    _scatter_by_group(X_reduced, 'NMDS1', 'NMDS2', features_list, None,
                      f"{title}  (stress {stress:.3f} - {quality})", 'NMDS1', 'NMDS2',
                      f"{output}/report/NMDS-{file_name}.png")

HEATMAP_MAX_INCHES = 22
HEATMAP_MAX_ANNOTATED_GROUPS = 25

def dissimilarity_heatmap(df, feature, output, title):
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import seaborn as sns

    prepared = _prepare_for_distance_tests(df, feature)
    if prepared is None:
        return None
    distance_matrix, _, labels = prepared
    label_values = np.asarray(labels)
    groups = np.unique(label_values)
    if len(groups) < 2:
        return None

    original = df[feature].dropna().astype(str)
    names = list(pd.unique(original))[:len(groups)] if len(pd.unique(original)) == len(groups) else [str(g) for g in groups]

    average = np.zeros((len(groups), len(groups)))
    for i, group_i in enumerate(groups):
        rows = np.where(label_values == group_i)[0]
        for j, group_j in enumerate(groups):
            columns = np.where(label_values == group_j)[0]
            block = distance_matrix[np.ix_(rows, columns)]
            if i == j:
                block = block[np.triu_indices(len(rows), k=1)] if len(rows) > 1 else block
            average[i, j] = float(np.mean(block)) if block.size else np.nan

    side = len(groups)
    plt.figure(figsize=(min(HEATMAP_MAX_INCHES, max(6, side)),
                        min(HEATMAP_MAX_INCHES, max(5, side * 0.8))))
    annotate = side <= HEATMAP_MAX_ANNOTATED_GROUPS
    sns.heatmap(pd.DataFrame(average, index=names, columns=names), annot=annotate, fmt=".2f",
                cmap=sns.light_palette(ROLE_COLOURS['batch'], as_cmap=True),
                linewidths=2 if annotate else 0, linecolor='white',
                xticklabels=True, yticklabels=True,
                cbar_kws={'label': 'average distance between samples'})
    if not annotate:
        plt.xticks(fontsize=5); plt.yticks(fontsize=5)
    plt.title(f"Average distance between {feature} groups\n(diagonal = spread inside a group)")
    plt.tight_layout()
    plt.savefig(f"{output}/report/{title}.png", dpi=int(setting('figure_dpi', 300)))
    plt.close()
    return average

def _r2_from_distance(distance_matrix, labels):
    import numpy as np
    label_values = np.asarray(labels)
    n = distance_matrix.shape[0]
    if n < 3:
        return None
    ss_total = np.sum(distance_matrix ** 2) / n
    if ss_total <= 0:
        return None
    ss_within = 0.0
    for group in np.unique(label_values):
        group_index = np.where(label_values == group)[0]
        if len(group_index) > 1:
            block = distance_matrix[np.ix_(group_index, group_index)]
            ss_within += np.sum(block ** 2) / len(group_index)
    return float((ss_total - ss_within) / ss_total)

def _stratified_resamples(batch_labels, phenotype_labels, fraction, repeats, rng):
    import numpy as np
    cells = {}
    for position, (batch, phenotype) in enumerate(zip(batch_labels, phenotype_labels)):
        cells.setdefault((batch, phenotype), []).append(position)

    resamples = []
    for _ in range(repeats):
        chosen = []
        for positions in cells.values():
            take = max(2, int(round(fraction * len(positions)))) if len(positions) > 2 else len(positions)
            take = min(take, len(positions))
            chosen.extend(rng.choice(positions, size=take, replace=False))
        resamples.append(np.sort(np.array(chosen, dtype=int)))
    return resamples

def kendalls_w(rankings):
    import numpy as np
    matrix = np.asarray(rankings, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 2:
        return None
    number_of_resamples, number_of_methods = matrix.shape
    rank_sums = matrix.sum(axis=0)
    mean_rank_sum = rank_sums.mean()
    deviation = float(np.sum((rank_sums - mean_rank_sum) ** 2))

    correction = 0.0
    for one_ranking in matrix:
        _, sizes = np.unique(one_ranking, return_counts=True)
        tied = sizes[sizes > 1].astype(float)
        correction += float(np.sum(tied ** 3 - tied))

    denominator = ((number_of_resamples ** 2) * (number_of_methods ** 3 - number_of_methods)
                   - number_of_resamples * correction)
    if denominator <= 0:
        return None
    return float(12.0 * deviation / denominator)

def stability_analysis(dataset_name, raw_data_folder, corrected_outputs, sample_id_column,
                       study_name, factor_of_interest, retained_variability=None,
                       lower_limit_variability=None, cleaned_folder=None):
    import stability
    return stability.analyse(dataset_name, raw_data_folder, corrected_outputs, sample_id_column,
                             study_name, factor_of_interest, cleaned_folder)

def stability_plot(result, output, title):
    import matplotlib.pyplot as plt
    import numpy as np
    if not result or not result.get('methods'):
        return None
    rows = [row for row in result['methods'] if row['selection-frequency'] is not None]
    if not rows:
        return None
    rows = rows[::-1]
    names = [row['method'] for row in rows]
    y = np.arange(len(rows))

    fig, (ax_left, ax_right) = plt.subplots(
        1, 2, figsize=(max(9.0, 1.6 + len(rows) * 0.42), max(4.2, len(rows) * 0.42) + 1.0),
        gridspec_kw={'width_ratios': (1, 1.25), 'wspace': 0.32})

    frequencies = [100.0 * row['selection-frequency'] for row in rows]
    best = max(range(len(rows)), key=lambda i: frequencies[i])
    colours = [ROLE_COLOURS['batch'] if i == best else NEUTRAL for i in range(len(rows))]
    ax_left.barh(y, frequencies, color=colours, height=0.62, zorder=3)
    for position, value in zip(y, frequencies):
        ax_left.annotate(f"{value:.0f}%", (value, position), xytext=(4, 0), textcoords='offset points',
                         va='center', fontsize=8, color=INK_SECONDARY)
    ax_left.set_yticks(y); ax_left.set_yticklabels(names, fontsize=9)
    ax_left.set_xlim(0, max(100.0, max(frequencies) * 1.18))
    style_axes(ax_left, title=None, xlabel="chosen in % of resamples", ylabel="")
    ax_left.grid(True, axis='x', color=GRID, linewidth=0.8, zorder=0)
    ax_left.set_title("How often each method won", color=INK, fontsize=10.5, pad=6)

    medians = [row['batch-retention-median'] for row in rows]
    lows = [row['batch-retention-low'] for row in rows]
    highs = [row['batch-retention-high'] for row in rows]
    for position, (median, low, high) in enumerate(zip(medians, lows, highs)):
        if median is None:
            continue
        ax_right.plot([low, high], [position, position], color=NEUTRAL, linewidth=3,
                      solid_capstyle='butt', zorder=3)
        ax_right.plot([median], [position], marker='o', markersize=7,
                      color=ROLE_COLOURS['batch'], markeredgecolor='white',
                      markeredgewidth=1.2, zorder=4)
    ax_right.set_yticks(y); ax_right.set_yticklabels([])
    style_axes(ax_right, title=None, xlabel="batch variability left behind (% of the original)", ylabel="")
    ax_right.grid(True, axis='x', color=GRID, linewidth=0.8, zorder=0)
    ax_right.set_title("Spread over the resamples (dot = median, bar = middle 95%)",
                       color=INK, fontsize=10.5, pad=6)

    concordance = result.get('kendalls-w')
    subtitle = (f"{result['decided']} of {result['resamples']} subsamples decided, "
                f"each holding {int(round(result['fraction'] * 100))}% of the samples")
    if concordance is not None:
        subtitle += f"   |   Kendall's W = {concordance:.2f}"
    fig.suptitle(f"Is the chosen method a stable choice?\n{subtitle}",
                 fontsize=11.5, color=INK, y=0.985, va='top')
    plt.tight_layout(rect=[0, 0, 1, 0.80])
    plt.savefig(f"{output}/report/{title}.png", dpi=300, facecolor='white')
    plt.close(fig)
    return True

def write_run_manifest(output_path, date, settings, datasets, method_outcomes):
    import json
    import platform
    import subprocess
    import sys

    def package_version(name):
        try:
            module = __import__(name)
            return getattr(module, '__version__', 'unknown')
        except Exception:
            return 'not installed'

    try:
        r_version = subprocess.run(["Rscript", "-e", "cat(R.version.string)"],
                                   capture_output=True, text=True, timeout=60).stdout.strip()
    except Exception:
        r_version = "unknown"

    manifest = {
        'bernard_run': {
            'date': date,
            'random_seed': RANDOM_STATE,
        },
        'settings': settings,
        'datasets': datasets,
        'methods': method_outcomes,
        'software': {
            'python': sys.version.split()[0],
            'platform': platform.platform(),
            'R': r_version,
            'packages': {name: package_version(name) for name in
                         ('numpy', 'pandas', 'scipy', 'sklearn', 'skbio', 'statsmodels',
                          'matplotlib', 'seaborn', 'inmoose')},
        },
    }
    path = f"{output_path}/run-manifest-{date}.json"
    with open(path, "w") as manifest_file:
        json.dump(manifest, manifest_file, indent=2, default=str)
    print(f"Run manifest written to {path}")
    return path

def delete_tmp_files(output_path):
    import os
    import glob
    #print("Temporary files will be deleted from directory.")
    # Create the pattern for files starting with "tmp" in the given directory
    pattern = os.path.join(output_path, '*tmp*')

    # Find all files that match the pattern
    tmp_files = glob.glob(pattern)

    # Loop through the files and delete them
    for file in tmp_files:
        try:
            os.remove(file)  # Delete the file
            #print(f"Deleted: {file}")
        except Exception as e:
            print(f"Failed to delete {file}: {e}")

def remove_tmp_from_filenames(corrected_outputs):
    import os
    # List all files in the directory
    files = os.listdir(corrected_outputs)
    for filename in files:
        # Define the current file path
        current_path = os.path.join(corrected_outputs, filename)
        # Skip directories and non-files
        if not os.path.isfile(current_path):
            continue
        # Check if '-tmp' exists in the filename
        if '-tmp' in filename:
            # Remove the '-tmp' substring
            new_name = filename.replace('-tmp', '')
            new_path = os.path.join(corrected_outputs, new_name)
            # Rename the file
            os.rename(current_path, new_path)
            #print(f"Renamed: {filename} -> {new_name}")
