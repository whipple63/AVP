
void play_with_lights() {
  
    for (uint8_t b=0; b<24; b++ ){
    bar.setBar(b, LED_RED);
  }
  for (uint8_t i=0; i<=15; i++) {
    bar.setBrightness(i);
    bar.writeDisplay();
    delay(20);
  }
  for (uint8_t j=0; j<=10; j++){
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_YELLOW);
    }
    bar.writeDisplay();
    delay(j);
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_RED);
    }
    bar.writeDisplay();
    delay(10-j);
  }

  for (uint8_t j=0; j<=10; j++){
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_GREEN);
    }
    bar.writeDisplay();
    delay(j);
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_YELLOW);
    }
    bar.writeDisplay();
    delay(10-j);
  }

  int bar_array[24];
  for (uint8_t b=0; b<24; b++ ){
    bar.setBar(b, LED_GREEN);
    bar_array[b] = 1;
  }
  bar.writeDisplay();
  
  for (uint8_t b=0; b<24; b++ ){
    int r = random(0,24);
    while (bar_array[r] != 1) { r = random(0,24); }
    bar_array[r] = 0;
    bar.setBar(r, LED_OFF);
    delay(10);
    bar.writeDisplay();
  }

}


void set_bar(int sensorValue) {
  if ( (millis() - LEDStartTime) > LEDonTime ) {
    for (uint8_t b=0; b<24; b++ ){
      bar_array[b] = LED_OFF;
    }
  } else {
    
    // This version sets bars to entire range of sensor
  //  float barStep = (maxVal - minVal) / 24;   // each bar represents one step
  //  int rangeLow = ceil((loThresh-minVal) / barStep);   // ceil so the transitional LED is red
  //  int rangeHi  = floor((hiThresh-minVal) / barStep);  // floor so the transitional LED is red
  //  int val      = round((sensorValue-minVal) / barStep);
  
    // This version leaves two red bars at each end
    float barStep = (hiThresh - loThresh) / 20;   // each bar represents one step
    int rangeLow = 2;
    int rangeHi  = 22;
    int val      = round((sensorValue-loThresh) / barStep) + rangeLow - 1;
  
    if (val < 0) { val = 0; }
    if (val > 23) { val = 23; }
  
  //  Serial.print(sensorValue);
  //  Serial.print("=");
  //  Serial.print(val);
  //  Serial.print(", ");
  //  Serial.print(loThresh);
  //  Serial.print("=");
  //  Serial.print(rangeLow);
  //  Serial.print(", ");
  //  Serial.print(hiThresh);
  //  Serial.print("=");
  //  Serial.println(rangeHi);
  
    // first set them all red
    for (uint8_t b=0; b<24; b++ ){
      bar_array[b] = LED_RED;
    }
    // set the bars that represent the working range yellow
    for (uint8_t b=rangeLow; b<rangeHi; b++ ){
      bar_array[b] = LED_GREEN;
    }
    // set the bar that represents the current value to yellow
    bar_array[val] = LED_YELLOW;
    
  }
  // display the bars
  for (uint8_t b=0; b<24; b++ ){
    bar.setBar(b, bar_array[b]);
  }
  bar.writeDisplay();
}

