#include <SPI.h>
#include <IntervalTimer.h>

#include "usb_dev.h"
#include "usb_serial.h"

// ============== SPI transmission =========================
// Pin definitions
const int chipSelectPin = 10;  // CS pin
const int INT_PIN = 1;

const int SCLK = 20000000;  // SCLK = 20 MHz

volatile float samplingRate = 392000.0; // 392 kHz
volatile float periodMicros = 1.0;

IntervalTimer timer; // Teensy-specific high-precision timer

volatile bool toggle = false; // Toggle flag for square wave

// ================= USB handshake definition ===========
// flags for states
volatile bool receiveSample = false; // initally, no samples will be considered.
volatile bool timerStart = false; //initially, no timer is working

#define MAX_BUFFER_SIZE 5120
#define HLAF_MAX_BUFFER_SIZE MAX_BUFFER_SIZE/2
#define PACKET_SIZE 512

uint8_t byte_buffer[MAX_BUFFER_SIZE]; //byte buffer (6*512 +2)
volatile int nextRead = 0;
volatile int nextWrite = 0;
volatile int buffer_size = 0;

volatile bool needToFill = false;
volatile bool end_of_file = false;

int coming_size; // coming size from PC, initilze here

// =============== Test LED def ===========
#define LED 2
#define LED2 3

#define LED_RED 33
#define LED_YELLOW 34

// =============== UART DEF ============
// set this to the hardware serial port you wish to use
#define HWSERIAL Serial7

void setup() {
  HWSERIAL.begin(115200); //begin HW serial

  SPI.begin();
  SPI.beginTransaction(SPISettings(SCLK, MSBFIRST, SPI_MODE0));

   // Configure chip select pin
  pinMode(chipSelectPin, OUTPUT);
  digitalWrite(chipSelectPin, HIGH);

  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);

  pinMode(LED_RED, OUTPUT);
  digitalWrite(LED_RED, LOW);

  pinMode(LED_YELLOW, OUTPUT);
  digitalWrite(LED_YELLOW, LOW);

  pinMode(LED2, OUTPUT);
  digitalWrite(LED2, HIGH); //to show this program start

  HWSERIAL.println("setup complete");


}

void loop() {

  if(receiveSample == false && timerStart == false){
    
    //wait for samplingrate
    if (usb_serial_available() == 4){
      uint8_t byte1, byte2, byte3, byte4;
      usb_serial_read(&byte1, 1);
      usb_serial_read(&byte2, 1);
      usb_serial_read(&byte3, 1);
      usb_serial_read(&byte4, 1);

      uint32_t sampleRate = (uint32_t) byte1 | (uint32_t) byte2 <<8 | (uint32_t) byte3 <<16 | (uint32_t) byte4 <<24;
      samplingRate = (float)sampleRate;
      periodMicros = 1e6/samplingRate;

      digitalWrite(LED, HIGH); //inidicate it has sampling rate 
      HWSERIAL.println("SR:");
      HWSERIAL.println(sampleRate);
      
      // if (samplingRate == 44000.0){
      //    digitalWrite(LED2, LOW);
      // }

      //clean buffer on MCU side
      nextRead = 0; 
      nextWrite = 0;
      buffer_size = 0;

      // uint8_t ACK = 'S';
      // usb_serial_write(&ACK, 1);

      receiveSample = true;

    }
  }else if (receiveSample == true && timerStart == false){
    //timer is not working so buffer_size is only incrementing

    // fill the first half buffer
    while(buffer_size <= (HLAF_MAX_BUFFER_SIZE - PACKET_SIZE) && end_of_file == false){ 
      //========= step 1: step 'S' to PC =======
      uint8_t ACK = 'S';
      usb_serial_write(&ACK, 1);

      //========= step 2: wait for coming bytes =======
      // Note: Use serial_avaible to continueouly check the coming data
      while(usb_serial_available() == 0){
        delay(0.2);
        continue;
        //do nothing just wait for coming bytes
      }

      //========= step 3: recive data and check for EOF by number of bytes =========
      coming_size = usb_serial_available();

      if (coming_size == 512){ // normal sample data(as we asked for 512 packet_size)
        // digitalWrite(LED2, LOW);
        int count = usb_serial_read(&byte_buffer[nextWrite], coming_size); //count should be the same as coming_size, just in case
        // nextWrite += count;
        nextWrite = (nextWrite + count) % MAX_BUFFER_SIZE;
        buffer_size += count;

      }else if(coming_size > 0){ // tail data, and stop reciving data
        int count = usb_serial_read(&byte_buffer[nextWrite], coming_size);
        // nextWrite += count;
        nextWrite = (nextWrite + count) % MAX_BUFFER_SIZE;
        buffer_size += count;
        digitalWrite(LED2, LOW); //recive end_of_file signal
        end_of_file = true;
        receiveSample = false;
        break; // Leave while loop
      }
    } //end while 

    //======== step 4: start timer to work ========
    timerStart = true;
    // Configure the timer for the desired period
    timer.begin(timerCallback, periodMicros);

    digitalWrite(LED_RED, HIGH); // indication for timer start

  }

  else if (receiveSample == true && timerStart == true){
    // HWSERIAL.println("SYN");
    //************** reciving sample and timer working at the same time *****************

    //we need to fill the first half buffer
    // HWSERIAL.println(nextRead);
    if(nextRead >=HLAF_MAX_BUFFER_SIZE && nextWrite == 0){ 
      HWSERIAL.println('1');
      while(nextWrite != HLAF_MAX_BUFFER_SIZE && end_of_file == false){ 
        // ======= step 1: send 'S' to ask for samples from PC ===========
        uint8_t ACK = 'S';
        usb_serial_write(&ACK, 1);

        //========= step 2: wait for coming bytes =======
        // Note: Use serial_avaible to continueouly check the coming data
        while(usb_serial_available() == 0){
          delay(0.2);
          //do nothing just wait for coming bytes
        }
        
        //========= step 3: recive data and check for EOF by number of bytes =========
        coming_size = usb_serial_available();

        if (coming_size == 512){ // normal sample data
          int count = usb_serial_read(&byte_buffer[nextWrite], coming_size);
          nextWrite = (nextWrite + count) % MAX_BUFFER_SIZE; 
          buffer_size += count;

        }
        else if(coming_size > 0){
          int count = usb_serial_read(&byte_buffer[nextWrite], coming_size);
          nextWrite = (nextWrite + count) % MAX_BUFFER_SIZE;
          buffer_size += count;
          digitalWrite(LED2, LOW); //recive end_of_file signal
          end_of_file = true;
          receiveSample = false;
          HWSERIAL.println("xxx");
          HWSERIAL.println(coming_size);
          break;
        }

        // if (usb_serial_available() == 0){
        //   digitalWrite(LED_YELLOW, HIGH);
        // }else{
        //   digitalWrite(LED_YELLOW, LOW);
        // }

        HWSERIAL.println("nextWrite");
        HWSERIAL.println(nextWrite);
      } //end while, mwans we fill up the first half of buffer

      HWSERIAL.println("nextWrite");
      HWSERIAL.println(nextWrite);

    } //end case: (nextRead >=HLAF_MAX_BUFFER_SIZE && nextWrite == 0)

    //fill the second half of buffer
    else if(nextRead < HLAF_MAX_BUFFER_SIZE && nextWrite == HLAF_MAX_BUFFER_SIZE){
      HWSERIAL.println('2');
      while(nextWrite != 0 && end_of_file == false){ 
        // ======= step 1: send 'S' to ask for samples from PC ===========
        uint8_t ACK = 'S';
        usb_serial_write(&ACK, 1);
        HWSERIAL.println('S');
        //========= step 2: wait for coming bytes =======
        // Note: Use serial_avaible to continueouly check the coming data
        while(usb_serial_available() == 0){
          delay(0.2);
          continue;
          //do nothing just wait for coming bytes
        }
        
        //========= step 3: recive data and check for EOF by number of bytes =========
        coming_size = usb_serial_available();

        if (coming_size == 512){ // normal sample data
          digitalWrite(LED2, LOW);
          int count = usb_serial_read(&byte_buffer[nextWrite], coming_size);
          nextWrite = (nextWrite + count) % MAX_BUFFER_SIZE;
          buffer_size += count;

        }else if(coming_size > 0 ){ //reach end_of_file
          int count = usb_serial_read(&byte_buffer[nextWrite], coming_size);
          nextWrite = (nextWrite + count) % MAX_BUFFER_SIZE;
          buffer_size += count;
          digitalWrite(LED2, LOW); //recive end_of_file signal
          end_of_file = true;
          receiveSample = false;
          break;
        }

        // if (usb_serial_available() == 0){
        //   digitalWrite(LED_YELLOW, HIGH);
        // }else{
        //   digitalWrite(LED_YELLOW, LOW);
        // }
        

      } //end while, means we fill up the second half of buffer

      HWSERIAL.println("nextWrite");
      HWSERIAL.println(nextWrite);
      HWSERIAL.println("nextRead");
      HWSERIAL.println(nextRead);

    } //end case: (nextRead < HLAF_MAX_BUFFER_SIZE && nextWrite == HLAF_MAX_BUFFER_SIZE)
  }
  else if (receiveSample == false && timerStart == true){
    //just do the SPI work and wait to end timer
    if (nextRead == nextWrite){
      // **** end the timer *****
      timer.end();
      digitalWrite(LED, LOW); //indicate stop timer

      // **** reset all flags *****
      timerStart = false;
      receiveSample = false;
      end_of_file = false;
    }
    

 
  }
  
}

void timerCallback() {
  // uint8_t low_byte = byte_buffer[nextRead];
  // uint8_t high_byte = byte_buffer[nextRead];
  if (receiveSample == false && nextRead == nextWrite){
    // timerStart = false;
    toggle = !toggle;
    digitalWrite(LED_YELLOW, HIGH);
  }
  else{
    uint16_t value = *(uint16_t*)&byte_buffer[nextRead];

    nextRead = (nextRead+2) % MAX_BUFFER_SIZE;
    buffer_size = buffer_size -2;
    
    // Transmit SPI data
    digitalWrite(chipSelectPin, LOW);
    SPI.transfer(highByte(value));
    SPI.transfer(lowByte(value));
    // SPI.transfer(high_byte);
    // SPI.transfer(low_byte);
    

    digitalWrite(chipSelectPin, HIGH);

    toggle = !toggle; // Toggle state for square wave
    // digitalWrite(INT_PIN, LOW);
  }
  
}




