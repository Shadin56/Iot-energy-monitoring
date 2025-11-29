# 🏫 IoT-Based Energy Monitoring System

Real-time energy monitoring and management system for academic buildings using Tuya smart devices and Streamlit.


## ✨ Features

- 📊 Real-time monitoring of voltage, current, power, and power factor
- 🏢 Hierarchical organization: Building → Classrooms → Devices
- 💰 Automatic energy cost calculation
- 🎛️ Remote device control (ON/OFF)
- 📈 Historical data analysis with customizable time ranges
- 📉 Visual analytics with trend charts
- 💾 Data export (CSV)
- 🐘 PostgreSQL support for cloud deployment

## 🚀 Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/FahimShahriarOvi/IoT-based-real-time-energy-monitoring-and-dashboard.git
cd IoT-based-real-time-energy-monitoring-and-dashboard

# Install dependencies
pip install -r requirements.txt

# Initialize database
python -c "from db import init_db; init_db()"

# Run application
streamlit run app.py
```

### Configuration

1. Get Tuya IoT credentials from [iot.tuya.com](https://iot.tuya.com)
2. Add devices through the dashboard UI
3. Configure energy cost in settings (default: 3.80 BDT/kWh)

## 📁 Project Structure

```
├── app.py              # Main Streamlit application
├── db.py               # Database operations
├── tuya_play.py        # Tuya API integration
├── requirements.txt    # Python dependencies 
└── Migration.py          # PostgreSQL migration script
```

## 🔧 Usage

### Add Classroom
1. Click "Add New Classroom" on home page
2. Enter classroom name (e.g., "FUB-101")

### Add Device
1. Select classroom
2. Click "Add New Device"
3. Enter device credentials:
   - Device Name
   - Tuya Access ID
   - Tuya Access Key
   - Tuya Device ID
   - API Endpoint

### Monitor Energy
- View real-time metrics on device dashboard
- Select time range for historical analysis
- Export data as CSV for reports

## 🐘 Cloud Deployment

### Option 1: Streamlit Cloud (Free)

1. Push code to GitHub
2. Sign up at [streamlit.io/cloud](https://streamlit.io/cloud)
3. Deploy from your repository
4. Add PostgreSQL database URL in secrets

### Option 2: Self-Hosted

```bash
# Set PostgreSQL URL
export DATABASE_URL="postgresql://user:pass@host:5432/db"

# Migrate existing data
python Migration.py

# Run app
streamlit run app.py
```

## 🛠️ Troubleshooting

### Device Not Responding
```bash
# Check device status and detect switch codes
python check_device_status.py
python detect_switch_codes.py
```

### View Device Data Points
```bash
# See all available data points for debugging
python show_device_datapoints.py
```

### Database Issues
```bash
# Add switch_code column if missing
python add_switch_code_column.py
```

## 📊 Supported Devices

- Tuya WiFi Smart Breakers (with power monitoring)
- Tuya 16A Smart Sockets (3-pin, power monitoring)
- Any Tuya-compatible device with energy monitoring

**Tested with:**
- Single switch devices (code: `switch`)
- Multi-gang switches (code: `switch_1`)

## 🔒 Security Notes

- Never commit credentials to GitHub
- Use environment variables or Streamlit secrets
- Add `.venv` and `secrets.toml` to `.gitignore`

## 📝 Requirements

```txt
streamlit>=1.28.0
pandas>=2.0.0
requests>=2.31.0
psycopg2-binary>=2.9.9
```

## 👥 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

## 📧 Contact

Project Link: [https://github.com/FahimShahriarOvi/IoT-based-real-time-energy-monitoring-and-dashboard]

## 🙏 Acknowledgments

- [Tuya IoT Platform](https://iot.tuya.com)
- [Streamlit](https://streamlit.io)
- East West University - CSE407 Green Computing Course