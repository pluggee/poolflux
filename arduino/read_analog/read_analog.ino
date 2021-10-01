void setup() {
  // put your setup code here, to run once:

  Serial.begin(9600);
  while (!Serial) {
    ; // wait for serial port to connect. Needed for native USB port only
  }
}

int val;

void loop() {
  // put your main code here, to run repeatedly:
  val = analogRead(9);
  Serial.println(val);
  delay(100);
}
