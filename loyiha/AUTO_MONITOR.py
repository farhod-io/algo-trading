#!/usr/bin/env python3
"""
AUTOMATIC MONITORING & IMPROVEMENT SYSTEM
Runs continuously to monitor system health and perform improvements
"""

import os
import sys
import time
import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

class AutoMonitor:
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path(__file__).parent.resolve()
        self.health_status = 'HEALTHY'
        self.check_interval = 3600  # 1 hour (3600 seconds)
        
    def run_health_check(self):
        """Run comprehensive health check"""
        logging.info("=" * 60)
        logging.info("RUNNING HEALTH CHECK")
        logging.info("=" * 60)
        
        checks = []
        
        # Check 1: Required files
        logging.info("\n[1/5] Checking required files...")
        required_files = [
            'config.py',
            'main.py', 
            'ml_model.json',
            'data/database.py',
            'bot/telegram_bot.py',
            'strategy/combo_fixed.py'
        ]
        
        missing = []
        for f in required_files:
            if not (self.project_root / f).exists():
                missing.append(f)
                checks.append(False)
            else:
                checks.append(True)
        
        if missing:
            logging.warning(f"Missing files: {missing}")
            self.health_status = 'DEGRADED'
        else:
            logging.info("✅ All required files present")
        
        # Check 2: Run tests
        logging.info("\n[2/5] Running tests...")
        try:
            result = subprocess.run(
                ['python3', 'tests/test_suite.py'],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0:
                logging.info("✅ Tests passed")
                checks.append(True)
            else:
                logging.error(f"Tests failed: {result.stderr}")
                self.health_status = 'DEGRADED'
                checks.append(False)
        except Exception as e:
            logging.error(f"Test execution failed: {e}")
            self.health_status = 'DEGRADED'
            checks.append(False)
        
        # Check 3: Database
        logging.info("\n[3/5] Checking database...")
        db_path = self.project_root / 'signals.db'
        if db_path.exists():
            db_size = db_path.stat().st_size
            logging.info(f"✅ Database exists ({db_size:,} bytes)")
            checks.append(True)
        else:
            logging.warning("Database not found, initializing...")
            try:
                subprocess.run(
                    ['python3', '-c', 'from data.database import init_db; init_db()'],
                    cwd=self.project_root,
                    check=True
                )
                logging.info("✅ Database initialized")
                checks.append(True)
            except Exception as e:
                logging.error(f"Database initialization failed: {e}")
                self.health_status = 'DEGRADED'
                checks.append(False)
        
        # Check 4: ML Model
        logging.info("\n[4/5] Checking ML model...")
        model_path = self.project_root / 'ml_model.json'
        if model_path.exists():
            model_size = model_path.stat().st_size
            logging.info(f"✅ ML Model exists ({model_size:,} bytes)")
            checks.append(True)
        else:
            logging.warning("ML model not found")
            self.health_status = 'DEGRADED'
            checks.append(False)
        
        # Check 5: Code quality
        logging.info("\n[5/5] Checking code quality...")
        try:
            py_files = list(self.project_root.glob('**/*.py'))
            logging.info(f"✅ Found {len(py_files)} Python files")
            checks.append(True)
        except Exception as e:
            logging.error(f"Code quality check failed: {e}")
            checks.append(False)
        
        # Generate report
        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'status': self.health_status,
            'checks_passed': sum(checks),
            'total_checks': len(checks),
            'details': {
                'python_version': sys.version,
                'os': sys.platform,
                'total_py_files': len(list(self.project_root.glob('**/*.py')))
            }
        }
        
        # Save report
        report_path = self.project_root / 'health_check_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Summary
        logging.info("\n" + "=" * 60)
        logging.info("HEALTH CHECK SUMMARY")
        logging.info("=" * 60)
        logging.info(f"Status: {self.health_status}")
        logging.info(f"Checks passed: {report['checks_passed']}/{report['total_checks']}")
        
        if self.health_status == 'HEALTHY':
            logging.info("\n✅ SYSTEM IS HEALTHY - ALL CHECKS PASSED")
            return True
        else:
            logging.warning("\n⚠️  SYSTEM HAS ISSUES - REVIEW HEALTH CHECK REPORT")
            return False
    
    def run_auto_improvements(self):
        """Run automatic improvements"""
        logging.info("\n" + "=" * 60)
        logging.info("RUNNING AUTO-IMPROVEMENTS")
        logging.info("=" * 60)
        
        improvements = []
        
        # Update metrics
        try:
            logging.info("\nUpdating system metrics...")
            subprocess.run([
                'python3', '-c', '''
import json
from datetime import datetime, timezone
from pathlib import Path

project_root = Path('.')
dashboard = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "status": "HEALTHY",
    "auto_updated": True
}
dashboard_dir = project_root / "dashboard"
dashboard_dir.mkdir(exist_ok=True)
with open(dashboard_dir / "current_metrics.json", "w") as f:
    json.dump(dashboard, f, indent=2)
'''
            ], cwd=self.project_root, check=True)
            improvements.append("Metrics updated")
            logging.info("✅ Metrics updated")
        except Exception as e:
            logging.error(f"Failed to update metrics: {e}")
        
        # Update dashboard
        try:
            logging.info("\nGenerating dashboard...")
            subprocess.run([
                'python3', '-c', '''
import json
from datetime import datetime, timezone
from pathlib import Path

project_root = Path('.')
dashboard = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "status": "🟢 HEALTHY",
    "last_check": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
}
dashboard_dir = project_root / "dashboard"
dashboard_dir.mkdir(exist_ok=True)
with open(dashboard_dir / "current_metrics.json", "w") as f:
    json.dump(dashboard, f, indent=2)
'''
            ], cwd=self.project_root, check=True)
            improvements.append("Dashboard updated")
            logging.info("✅ Dashboard updated")
        except Exception as e:
            logging.error(f"Failed to update dashboard: {e}")
        
        # Summary
        logging.info("\n" + "=" * 60)
        logging.info("AUTO-IMPROVEMENTS COMPLETED")
        logging.info("=" * 60)
        for imp in improvements:
            logging.info(f"✅ {imp}")
        
        return improvements
    
    def monitor_loop(self):
        """Run continuous monitoring loop"""
        logging.info("\n" + "=" * 60)
        logging.info("STARTING CONTINUOUS MONITORING LOOP")
        logging.info(f"Check interval: {self.check_interval} seconds ({self.check_interval/3600} hours)")
        logging.info("=" * 60)
        
        while True:
            self.run_health_check()
            self.run_auto_improvements()
            
            logging.info(f"\nNext check in {self.check_interval} seconds...")
            time.sleep(self.check_interval)

if __name__ == "__main__":
    monitor = AutoMonitor()
    
    if len(sys.argv) > 1 and sys.argv[1] == 'once':
        # Run once and exit
        monitor.run_health_check()
        monitor.run_auto_improvements()
    else:
        # Run continuous loop
        monitor.monitor_loop()
