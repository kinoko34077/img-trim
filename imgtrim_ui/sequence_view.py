"""Tkinter widget construction for the sequence capture screen."""

from tkinter import ttk


def build_capture_ui(app) -> None:
    """Create screen widgets and connect them to the capture controller."""

    main = ttk.Frame(
        app.root,
        padding=18
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
    # 保存先
    # ====================================================

    save_frame = ttk.LabelFrame(
        main,
        text="保存先",
        padding=12
    )

    save_frame.grid(
        row=0,
        column=0,
        sticky="ew",
        pady=(0, 10)
    )

    save_frame.columnconfigure(
        0,
        weight=1
    )

    ttk.Entry(
        save_frame,
        textvariable=
            app.output_dir
    ).grid(
        row=0,
        column=0,
        sticky="ew",
        padx=(0, 8)
    )

    ttk.Button(
        save_frame,
        text="参照",
        command=
            app.choose_output
    ).grid(
        row=0,
        column=1
    )


    # ====================================================
    # 撮影領域
    # ====================================================

    region = ttk.LabelFrame(
        main,
        text="撮影領域",
        padding=12
    )

    region.grid(
        row=1,
        column=0,
        sticky="ew",
        pady=(0, 10)
    )

    region_values = [
        (
            app.region_label_vars[0],
            app.region_x
        ),
        (
            app.region_label_vars[1],
            app.region_y
        ),
        (
            app.region_label_vars[2],
            app.region_w
        ),
        (
            app.region_label_vars[3],
            app.region_h
        )
    ]

    for i, (
        label_var,
        variable
    ) in enumerate(
        region_values
    ):

        ttk.Label(
            region,
            textvariable=label_var
        ).grid(
            row=0,
            column=i * 2,
            padx=(0, 4)
        )

        ttk.Spinbox(
            region,
            textvariable=variable,
            from_=-100000,
            to=100000,
            increment=1,
            width=9,
            justify="center"
        ).grid(
            row=0,
            column=
                i * 2 + 1,
            padx=(0, 10)
        )

    ttk.Label(
        region,
        text="input mode"
    ).grid(
        row=1,
        column=0,
        sticky="w",
        pady=(10, 0)
    )

    ttk.Combobox(
        region,
        textvariable=app.region_input_mode,
        values=(
            "corners",
            "center_abs",
            "size"
        ),
        state="readonly",
        width=14
    ).grid(
        row=1,
        column=1,
        columnspan=2,
        sticky="w",
        pady=(10, 0)
    )

    ttk.Checkbutton(
        region,
        text="\u5bfe\u8c61\u30a6\u30a3\u30f3\u30c9\u30a6\u3092\u57fa\u6e96\u306b\u3059\u308b",
        variable=app.relative_to_window,
        command=app.on_region_mode_changed
    ).grid(
        row=2,
        column=0,
        columnspan=8,
        sticky="w",
        pady=(10, 0)
    )

    ttk.Button(
        region,
        text="画面から範囲指定",
        command=
            app.prepare_region_select
    ).grid(
        row=3,
        column=0,
        columnspan=8,
        pady=(12, 0)
    )

    ttk.Label(
        region,
        text=(
            "ドラッグ中はカーソル周辺を拡大表示。"
            "確定後はX / Y / 幅 / 高さを"
            "1px単位で調整できます。"
        )
    ).grid(
        row=4,
        column=0,
        columnspan=8,
        pady=(8, 0)
    )

    ttk.Label(
        region,
        textvariable=app.region_summary,
        justify="left"
    ).grid(
        row=5,
        column=0,
        columnspan=8,
        sticky="w",
        pady=(6, 0)
    )


    # ====================================================
    # ページ制御
    # ====================================================

    page = ttk.LabelFrame(
        main,
        text="ページ制御",
        padding=12
    )

    page.grid(
        row=2,
        column=0,
        sticky="ew",
        pady=(0, 10)
    )

    ttk.Label(
        page,
        text="ページ送りキー"
    ).grid(
        row=0,
        column=0,
        sticky="w"
    )

    ttk.Entry(
        page,
        textvariable=
            app.page_key,
        state="readonly",
        width=15
    ).grid(
        row=0,
        column=1,
        padx=(8, 8)
    )

    ttk.Button(
        page,
        text="キー入力で設定",
        command=
            app.capture_page_key
    ).grid(
        row=0,
        column=2
    )


    ttk.Label(
        page,
        text="開始ページ"
    ).grid(
        row=1,
        column=0,
        sticky="w",
        pady=(10, 0)
    )

    ttk.Spinbox(
        page,
        textvariable=
            app.start_page,
        from_=1,
        to=999999,
        width=10
    ).grid(
        row=1,
        column=1,
        sticky="w",
        padx=(8, 0),
        pady=(10, 0)
    )


    ttk.Label(
        page,
        text="終了ページ"
    ).grid(
        row=1,
        column=2,
        sticky="w",
        padx=(20, 0),
        pady=(10, 0)
    )

    ttk.Spinbox(
        page,
        textvariable=
            app.end_page,
        from_=1,
        to=999999,
        width=10
    ).grid(
        row=1,
        column=3,
        sticky="w",
        padx=(8, 0),
        pady=(10, 0)
    )


    ttk.Label(
        page,
        text="現在ページ"
    ).grid(
        row=2,
        column=0,
        sticky="w",
        pady=(10, 0)
    )

    ttk.Spinbox(
        page,
        textvariable=
            app.current_page,
        from_=1,
        to=999999,
        width=10
    ).grid(
        row=2,
        column=1,
        sticky="w",
        padx=(8, 0),
        pady=(10, 0)
    )


    # ====================================================
    # timing
    # ====================================================

    timing = ttk.LabelFrame(
        main,
        text="タイミング",
        padding=12
    )

    timing.grid(
        row=3,
        column=0,
        sticky="ew",
        pady=(0, 10)
    )

    ttk.Label(
        timing,
        text="撮影後待機 (ms)"
    ).grid(
        row=0,
        column=0,
        sticky="w"
    )

    ttk.Spinbox(
        timing,
        textvariable=
            app.capture_delay,
        from_=0,
        to=60000,
        width=10
    ).grid(
        row=0,
        column=1,
        padx=(8, 25)
    )


    ttk.Label(
        timing,
        text=
            "ページ送り後待機 (ms)"
    ).grid(
        row=0,
        column=2,
        sticky="w"
    )

    ttk.Spinbox(
        timing,
        textvariable=
            app.page_delay,
        from_=0,
        to=60000,
        width=10
    ).grid(
        row=0,
        column=3,
        padx=(8, 0)
    )


    # ====================================================
    # 保存形式
    # ====================================================

    naming = ttk.LabelFrame(
        main,
        text="保存形式",
        padding=12
    )

    naming.grid(
        row=4,
        column=0,
        sticky="ew",
        pady=(0, 10)
    )

    ttk.Label(
        naming,
        text="ファイル名接頭辞"
    ).grid(
        row=0,
        column=0
    )

    ttk.Entry(
        naming,
        textvariable=
            app.prefix,
        width=20
    ).grid(
        row=0,
        column=1,
        padx=(8, 20)
    )

    ttk.Label(
        naming,
        text=(
            "PNG / compress_level=1"
            "（低圧縮・可逆）"
        )
    ).grid(
        row=0,
        column=2
    )

    ttk.Checkbutton(
        naming,
        text="\u65e2\u5b58\u30d5\u30a1\u30a4\u30eb\u3092\u4e0a\u66f8\u304d",
        variable=app.overwrite_existing
    ).grid(
        row=1,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(8, 0)
    )

    ttk.Label(
        naming,
        text="\u4e0a\u66f8\u304d\u3057\u306a\u3044\u5834\u5408\u306e\u63a5\u5c3e\u8f9e"
    ).grid(
        row=1,
        column=2,
        sticky="e",
        padx=(12, 8),
        pady=(8, 0)
    )

    ttk.Entry(
        naming,
        textvariable=app.filename_suffix,
        width=14
    ).grid(
        row=1,
        column=3,
        sticky="w",
        pady=(8, 0)
    )

    ttk.Label(
        naming,
        text="\u9023\u756a\u6841\u6570"
    ).grid(
        row=2,
        column=0,
        sticky="w",
        pady=(8, 0)
    )

    ttk.Spinbox(
        naming,
        textvariable=app.filename_digits,
        from_=1,
        to=12,
        width=6
    ).grid(
        row=2,
        column=1,
        sticky="w",
        padx=(8, 20),
        pady=(8, 0)
    )

    ttk.Label(
        naming,
        text="\u4fdd\u5b58\u9023\u756a\u958b\u59cb"
    ).grid(
        row=2,
        column=2,
        sticky="e",
        padx=(12, 8),
        pady=(8, 0)
    )

    ttk.Spinbox(
        naming,
        textvariable=app.filename_start,
        from_=0,
        to=999999999,
        width=10
    ).grid(
        row=2,
        column=3,
        sticky="w",
        pady=(8, 0)
    )


    # ====================================================
    # 状態
    # ====================================================

    ttk.Label(
        main,
        textvariable=
            app.target_name
    ).grid(
        row=5,
        column=0,
        pady=(2, 4)
    )

    ttk.Label(
        main,
        textvariable=
            app.status
    ).grid(
        row=6,
        column=0,
        pady=(2, 8)
    )

    app.progress = (
        ttk.Progressbar(
            main,
            mode="determinate"
        )
    )

    app.progress.grid(
        row=7,
        column=0,
        sticky="ew",
        pady=(0, 12)
    )


    # ====================================================
    # Buttons
    # ====================================================

    buttons = ttk.Frame(
        main
    )

    buttons.grid(
        row=8,
        column=0
    )

    app.start_button = ttk.Button(
        buttons,
        text="開始",
        command=
            app.start_capture
    )

    app.start_button.grid(
        row=0,
        column=0,
        padx=5
    )

    app.pause_button = ttk.Button(
        buttons,
        text="一時停止",
        command=
            app.toggle_pause
    )

    app.pause_button.grid(
        row=0,
        column=1,
        padx=5
    )

    ttk.Button(
        buttons,
        text="停止",
        command=
            app.stop_capture
    ).grid(
        row=0,
        column=2,
        padx=5
    )

    ttk.Button(
        buttons,
        text="\u30c8\u30ea\u30df\u30f3\u30b0",
        command=
            app.open_trim_tool
    ).grid(
        row=0,
        column=3,
        padx=5
    )

    ttk.Label(
        main,
        text=
            "Esc：一時停止 / 再開"
    ).grid(
        row=9,
        column=0,
        pady=(10, 0)
    )
