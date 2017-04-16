lambda.zip: lambda
	cd lambda && zip -qr ../lambda.zip .

lambda:
	mkdir -p lambda
	pip install -r requirements.txt -t lambda
	cp compare.py lambda/compare.py

clean:
	rm -rf lambda lambda.zip