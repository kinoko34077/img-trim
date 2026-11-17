"""Tkinter widget construction for the batch trimming screen."""

from tkinter import ttk


def build_trim_ui(app) -> None:
    """Create trimming controls and connect them to the app controller."""

    main = ttk.Frame(
        app.root,
        padding=20
    )

    main.pack(
        fill="both",
        expand=True
    )

    main.columnconfigure(
        0,
        weight=1
    )


    # ====================================================
    # 入力フォルダ
    # ====================================================

    ttk.Label(
        main,
        text="入力フォルダ"
    ).grid(
        row=0,
        column=0,
        sticky="w"
    )

    input_frame = ttk.Frame(main)

    input_frame.grid(
        row=1,
        column=0,
        sticky="ew",
        pady=(5, 15)
    )

    input_frame.columnconfigure(
        0,
        weight=1
    )

    ttk.Entry(
        input_frame,
        textvariable=app.input_dir
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 10)
    )

    ttk.Button(
        input_frame,
        text="参照",
        command=app.select_input
    ).grid(
        row=0,
        column=1
    )


    # ====================================================
    # 出力フォルダ
    # ====================================================

    ttk.Label(
        main,
        text="出力フォルダ"
    ).grid(
        row=2,
        column=0,
        sticky="w"
    )

    output_frame = ttk.Frame(main)

    output_frame.grid(
        row=3,
        column=0,
        sticky="ew",
        pady=(5, 15)
    )

    output_frame.columnconfigure(
        0,
        weight=1
    )

    ttk.Entry(
        output_frame,
        textvariable=app.output_dir
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 10)
    )

    ttk.Button(
        output_frame,
        text="参照",
        command=app.select_output
    ).grid(
        row=0,
        column=1
    )


    # ====================================================
    # トリミング設定
    # ====================================================

    trim_frame = ttk.LabelFrame(
        main,
        text="トリミング量（px）",
        padding=20
    )

    trim_frame.grid(
        row=4,
        column=0,
        sticky="ew",
        pady=(5, 15)
    )

    # 5列にして中央へ十字配置
    for column in range(5):
        trim_frame.columnconfigure(
            column,
            weight=1
        )


    # --------------------
    # 上
    # --------------------

    ttk.Label(
        trim_frame,
        text="上"
    ).grid(
        row=0,
        column=2,
        pady=(0, 3)
    )

    ttk.Entry(
        trim_frame,
        textvariable=app.top,
        width=10,
        justify="center"
    ).grid(
        row=1,
        column=2
    )


    # --------------------
    # 左・右
    # --------------------

    ttk.Label(
        trim_frame,
        text="左"
    ).grid(
        row=2,
        column=0,
        pady=(18, 3)
    )

    ttk.Label(
        trim_frame,
        text="右"
    ).grid(
        row=2,
        column=4,
        pady=(18, 3)
    )

    ttk.Entry(
        trim_frame,
        textvariable=app.left,
        width=10,
        justify="center"
    ).grid(
        row=3,
        column=0
    )

    # 中央は単なる表示
    ttk.Label(
        trim_frame,
        text="画像"
    ).grid(
        row=3,
        column=2
    )

    ttk.Entry(
        trim_frame,
        textvariable=app.right,
        width=10,
        justify="center"
    ).grid(
        row=3,
        column=4
    )


    # --------------------
    # 下
    # --------------------

    ttk.Label(
        trim_frame,
        text="下"
    ).grid(
        row=4,
        column=2,
        pady=(18, 3)
    )

    ttk.Entry(
        trim_frame,
        textvariable=app.bottom,
        width=10,
        justify="center"
    ).grid(
        row=5,
        column=2
    )


    # ====================================================
    # サブフォルダ
    # ====================================================

    ttk.Checkbutton(
        main,
        text="サブフォルダも実行",
        variable=app.include_subfolders,
        command=app.save_settings
    ).grid(
        row=5,
        column=0,
        sticky="w",
        pady=(0, 15)
    )


    # ====================================================
    # 実行
    # ====================================================

    app.run_button = ttk.Button(
        main,
        text="トリミング実行",
        command=app.run_trim
    )

    app.run_button.grid(
        row=6,
        column=0,
        pady=(5, 15)
    )


    # ====================================================
    # 状態
    # ====================================================

    ttk.Label(
        main,
        textvariable=app.status
    ).grid(
        row=7,
        column=0,
        pady=(0, 8)
    )


    # ====================================================
    # プログレスバー
    # ====================================================

    app.progress = ttk.Progressbar(
        main,
        mode="determinate"
    )

    app.progress.grid(
        row=8,
        column=0,
        sticky="ew"
    )
