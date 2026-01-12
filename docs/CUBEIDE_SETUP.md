# Draw.io Export and CubeIDE Manual Steps

## 0. Exporting Draw.io Diagrams to Images

### Option A: VS Code Draw.io Extension (Recommended)
1. Install the **Draw.io Integration** extension in VS Code (by Henning Dieterichs)
2. Open any `.drawio` file
3. Click **File → Export** or use the export button in the toolbar
4. Choose **PNG** or **SVG** format
5. Save to `docs/schematics/images/` subfolder

### Option B: Draw.io Desktop App
1. Download from [app.diagrams.net](https://app.diagrams.net) or as desktop app
2. Open the `.drawio` file
3. **File → Export as → PNG/SVG/PDF**
4. Save to desired location

### Option C: Command Line (requires draw.io-export npm package)
```bash
npm install -g draw.io-export
drawio-export docs/schematics/*.drawio -o docs/schematics/images/ -f png
```
Note: This requires Node.js and may have compatibility issues on Windows.

---

## 1. STM32CubeIDE Manual Configuration Steps

**Open the project in STM32CubeIDE and double-click `capstone test.ioc`**

### Step 1: Configure MUX Select Pins (PB0, PB1, PB2)

| Pin | Current | Change To | Label |
|-----|---------|-----------|-------|
| PB0 | Not configured | GPIO_Output | MUX_S0 |
| PB1 | ADC3_IN1 | GPIO_Output | MUX_S1 |
| PB2 | Not configured | GPIO_Output | MUX_S2 |

**How:**
1. In Pinout view, click on **PB0** → Select **GPIO_Output**
2. Right-click → **Enter User Label** → Type `MUX_S0`
3. Repeat for PB1 and PB2

### Step 2: Configure Row Mux Enable Pins (PC0-PC4)

| Pin | Current | Change To | Label |
|-----|---------|-----------|-------|
| PC0 | GPIO_Output (ROW_DRIVE_1) | GPIO_Output | ROW_MUX0_EN |
| PC1 | GPIO_Output (ROW_DRIVE_0) | GPIO_Output | ROW_MUX1_EN |
| PC2 | ADCx_IN8 | GPIO_Output | ROW_MUX2_EN |
| PC3 | Not configured | GPIO_Output | ROW_MUX3_EN |
| PC4 | ADC2_IN5 | GPIO_Output | ROW_MUX4_EN |

### Step 3: Configure Column Mux Enable Pins (PC5-PC9)

| Pin | Current | Change To | Label |
|-----|---------|-----------|-------|
| PC5 | Not configured | GPIO_Output | COL_MUX0_EN |
| PC6 | Not configured | GPIO_Output | COL_MUX1_EN |
| PC7 | Not configured | GPIO_Output | COL_MUX2_EN |
| PC8 | Not configured | GPIO_Output | COL_MUX3_EN |
| PC9 | Not configured | GPIO_Output | COL_MUX4_EN |

### Step 4: Configure Analog Pins

| Pin | Current | Change To | Label |
|-----|---------|-----------|-------|
| PA0 | ADC1_IN1 | **Keep as ADC1_IN1** | ADC_COL_SENSE |
| PA1 | ADC1_IN2 | GPIO_Output | ROW_DRIVE |

### Step 5: Save and Generate Code

1. Press **Ctrl+S** to save the `.ioc` file
2. Click **Yes** when asked to generate code
3. The HAL initialization functions in `main.c` will be updated
4. Your USER CODE sections will be preserved!

### Step 6: Verify GPIO Init in main.c

After regeneration, check `MX_GPIO_Init()` function to ensure:
- All PCx pins are configured as outputs
- All PBx pins are configured as outputs
- PA1 is configured as output

---

## Pin Configuration Summary

```
BEFORE (2x2 system):        AFTER (40x40 system):
________________________    ________________________________
PC0: ROW_DRIVE_1      →    PC0: ROW_MUX0_EN
PC1: ROW_DRIVE_0      →    PC1: ROW_MUX1_EN
PA0: ADC1_IN1         →    PA0: ADC1_IN1 (unchanged)
PA1: ADC1_IN2         →    PA1: ROW_DRIVE (GPIO out)

NEW PINS:
PB0, PB1, PB2: MUX_S0, MUX_S1, MUX_S2
PC2, PC3, PC4: ROW_MUX2_EN, ROW_MUX3_EN, ROW_MUX4_EN
PC5-PC9: COL_MUX0_EN through COL_MUX4_EN
```

---

## Reverting Changes

If something goes wrong with the `.ioc` file:

1. **Git revert:** `git checkout -- "capstone test.ioc"`
2. **Re-download from GitHub:** The original is at your repo
3. **Backup:** I recommend committing before making changes!
