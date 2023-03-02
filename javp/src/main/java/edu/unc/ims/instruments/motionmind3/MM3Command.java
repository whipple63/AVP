package edu.unc.ims.instruments.motionmind3;

public class MM3Command  {

  /**
   * The command that will be sent
   */
  private String mCommand;  

  /*
   *
   */
  private String mResult = "";

 
  public MM3Command(String command) {
    mCommand = command;
  }

  public static String buildCommand(Type type, long parameter) {
      return CommandStrings[type.ordinal()] + " " + String.format("%02d", parameter) + "\r\n";
    }

  public static String buildCommand(Type type, long parameter, long value) {
      return CommandStrings[type.ordinal()] + " "
              + String.format("%02d", parameter) + " "
              + Long.toString(value) + "\r\n";
    }

    public static String buildCommand(Type type, MM3.MM3Parameter parameter) {
      return CommandStrings[type.ordinal()] + " " + String.format("%02d", parameter.ordinal()) + "\r\n";
    }

    public static String buildCommand(Type type, MM3.MM3Parameter parameter,
            long value) {
      return CommandStrings[type.ordinal()] + " " + String.format("%02d", parameter.ordinal()) + " " +
              Long.toString(value) + "\r\n";
    }

  public String getCommand() {
    return mCommand;
  }
  
  public String getResult() {
    return mResult;
  }

  public void setResult(String result) {
    mResult = result;
  }

  public enum Type {
    READ, WRITE, WRITE_ST, MOVE_ABS, MOVE_REL, MOVE_AT, CH_SPD, RESET
  };
  private static final String[] CommandStrings = {
    "R01", "W01", "S01", "P01", "M01", "V01", "C01", "Y01"
  };
}
