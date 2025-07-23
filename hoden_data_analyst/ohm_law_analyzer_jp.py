import pandas as pd
import matplotlib.pyplot as plt
import japanize_matplotlib  # Matplotlibの日本語表示を有効化
import os
import glob
import re

def parse_value_from_filename(filename, pattern, unit_map):
    """
    ファイル名から正規表現で値を抽出し、数値に変換する汎用関数。
    """
    basename = os.path.basename(filename)
    match = re.search(pattern, basename)
    if not match:
        return None
    
    value_str = match.group(1)
    value = int(value_str)

    # 単位に基づく乗算（k, Mなど）
    if len(match.groups()) > 1 and match.group(2) in unit_map:
        unit = match.group(2)
        return value * unit_map[unit]
    
    return value

def analyze_experiment_data():
    """
    フォルダ内の複数の実験データCSVを自動で読み込み、
    電流を計算し、結果をファイルごとに出力。
    さらに、気圧ごとにデータを集約したCSVと、全体のグラフを出力する。
    """
    # --- ★★★ 設定項目 ★★★ ---
    # 解析したいデータが入っているフォルダ名を指定します。
    # 例: 'data_set_1'
    # 空文字 ('') にすると、このスクリプトと同じ場所にあるファイルを探します。
    TARGET_FOLDER = '20250723_1'  # ← ここを編集してください

    # 解析したい特定の気圧を指定します (例: 200)。
    # すべての気圧を解析する場合は None を設定します。
    TARGET_PRESSURE = 300  # ← ここを編集してください
    # --- ★★★★★★★★★★★ ---

    # --- 1. 対象となるCSVファイルをすべて見つける ---
    if TARGET_FOLDER:
        # ターゲットフォルダが指定されている場合
        if not os.path.isdir(TARGET_FOLDER):
            print(f"❌ エラー: フォルダ '{TARGET_FOLDER}' が見つかりません。")
            return
        file_pattern = os.path.join(TARGET_FOLDER, '*_hoden.csv')
        search_location_msg = f"フォルダ '{TARGET_FOLDER}'"
    else:
        # ターゲットフォルダが指定されていない場合（従来通り）
        file_pattern = '*_hoden.csv'
        search_location_msg = "現在のフォルダ"

    csv_files = glob.glob(file_pattern)

    if not csv_files:
        print(f"❌ エラー: {search_location_msg} 内で '{os.path.basename(file_pattern)}' に一致するファイルが見つかりません。")
        return

    print(f"✅ {search_location_msg} で {len(csv_files)}個のデータファイルが見つかりました。")
    if TARGET_PRESSURE is not None:
        print(f"🎯 ターゲット気圧: {TARGET_PRESSURE} Pa のデータのみを解析します。")
    print("-" * 40)

    # 全てのデータを集約するリスト
    all_processed_data = []

    # --- 2. 各ファイルを個別に処理 ---
    for filepath in csv_files:
        # ファイル名から気圧を取得
        pressure = parse_value_from_filename(filepath, r'(\d+)Pa', {})

        # --- 特定の気圧のみを対象とするフィルター ---
        if TARGET_PRESSURE is not None and pressure != TARGET_PRESSURE:
            continue  # ターゲットの気圧でなければこのファイルをスキップ

        print(f"🔄 ファイルを処理中: {filepath}")
        
        # ファイル名から抵抗値を取得
        resistance_ch2 = parse_value_from_filename(filepath, r'(\d+)([kM])ohm', {'k': 1000, 'M': 1000000})

        if resistance_ch2 is None:
            print(f"⚠️ 警告: {filepath} から抵抗値を抽出できませんでした。スキップします。")
            continue
        if pressure is None:
            print(f"⚠️ 警告: {filepath} から気圧を抽出できませんでした。スキップします。")
            continue
            
        try:
            # まずは全ての列を文字列として読み込む
            df = pd.read_csv(filepath, header=None, dtype=str)
            COL_V_CH1 = 1
            COL_V_CH2 = 5

            # 1列目がタイムスタンプ形式 (HH:MM:SS) の行のみを保持する
            time_format_regex = r'^\d{2}:\d{2}:\d{2}$'
            original_rows = len(df)
            df = df[df[0].str.match(time_format_regex, na=False)].copy()
            print(f"  -> フッターを除外: {original_rows}行から{len(df)}行にフィルタリングしました。")
            
            # 電圧の列を文字列(str)から数値(numeric)に変換します。
            df[COL_V_CH1] = pd.to_numeric(df[COL_V_CH1], errors='coerce')
            df[COL_V_CH2] = pd.to_numeric(df[COL_V_CH2], errors='coerce')

            # 電圧値が無効(NaN)になった行をデータから削除します。
            df.dropna(subset=[COL_V_CH1, COL_V_CH2], inplace=True)

            # --- 3. 電流を計算 ---
            current_ch2 = df[COL_V_CH2] / resistance_ch2
            resistance_ch1 = 10_000_000
            current_ch1 = df[COL_V_CH1] / resistance_ch1
            final_current = current_ch2 - current_ch1

            # --- 4. 処理済みCSVをファイルごとに出力 ---
            df_to_save = df.copy()
            df_to_save['final_current_A'] = final_current
            output_filepath = filepath.replace('_hoden.csv', '_processed.csv')
            df_to_save.to_csv(output_filepath, header=False, index=False)
            print(f"  -> ✅ 計算結果を '{output_filepath}' に保存しました。")

            # 集約用にデータを準備
            processed_df = pd.DataFrame({
                'voltage_ch1_V': df[COL_V_CH1],
                'final_current_A': final_current,
                'resistance_ohm': resistance_ch2,
                'pressure_Pa': pressure
            })
            all_processed_data.append(processed_df)

        except Exception as e:
            print(f"❌ エラー: {filepath} の処理中にエラーが発生しました: {e}")

    if not all_processed_data:
        print(f"\n❌ 処理対象のデータ（気圧 {TARGET_PRESSURE} Pa）が見つかりませんでした。")
        return

    # --- 5. 全てのデータを一つのデータフレームに結合 ---
    final_df = pd.concat(all_processed_data, ignore_index=True)
    
    # --- 6. 気圧ごとにデータを集約してCSVファイルに出力 ---
    print("\n📑 気圧ごとにデータを集約してCSVファイルを作成します...")
    grouped_by_pressure = final_df.groupby('pressure_Pa')

    for pressure_val, group_df in grouped_by_pressure:
        summary_filename = f'summary_iv_{pressure_val}Pa.csv'
        # 保存先パスを決定
        summary_filepath = os.path.join(TARGET_FOLDER, summary_filename)
        summary_df = group_df[['voltage_ch1_V', 'final_current_A']]
        summary_df.to_csv(summary_filepath, index=False)
        print(f"  -> ✅ 気圧別サマリーファイルを保存しました: {summary_filepath}")
    
    # --- 7. 全体の電流-電圧特性グラフのプロット ---
    print("\n📊 全データを統合してグラフを作成します...")
    plt.style.use('seaborn-v0_8-whitegrid')
    fig, ax = plt.subplots(figsize=(12, 8))

    # グラフのタイトルとファイル名を動的に設定
    if TARGET_PRESSURE is not None:
        plot_title = f'電流-電圧特性グラフ ({TARGET_PRESSURE} Pa)'
        plot_filename = f'current_voltage_characteristics_plot_{TARGET_PRESSURE}Pa.png'
    else:
        plot_title = '電流-電圧特性グラフ (全データ)'
        plot_filename = 'current_voltage_characteristics_plot_final.png'

    # 保存先パスを決定
    plot_filepath = os.path.join(TARGET_FOLDER, plot_filename)

    unique_resistances = sorted(final_df['resistance_ohm'].unique())
    for res in unique_resistances:
        subset = final_df[final_df['resistance_ohm'] == res]
        if res >= 1_000_000:
            label_text = f'{res / 1_000_000:g} MΩ'
        else:
            label_text = f'{res / 1_000:g} kΩ'
            
        ax.plot(subset['voltage_ch1_V'], subset['final_current_A'], 
                marker='o', markersize=2, linestyle='', alpha=0.6, label=label_text)

    ax.set_title(plot_title, fontsize=16, fontweight='bold')
    ax.set_xlabel('CH1 電圧 (V)', fontsize=14)
    ax.set_ylabel('最終電流 (A) [CH2電流 - CH1電流]', fontsize=14)
    ax.legend(title='CH2 抵抗値', fontsize=12, title_fontsize=13)
    ax.minorticks_on()
    ax.grid(which='both', linestyle=':', linewidth='0.5')
    
    plt.savefig(plot_filepath, dpi=300)
    print(f"✅ グラフを '{plot_filepath}' として保存しました。")

if __name__ == '__main__':
    analyze_experiment_data()
