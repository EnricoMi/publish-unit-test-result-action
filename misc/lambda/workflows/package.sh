mkdir -p package
pip install --target package -r requirements.txt
(cd package; zip -r ../package.zip .)
zip package.zip service.py

