using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Automation;
using System.ComponentModel;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using System.IO;
using System.Net;
using System.Threading;
using System.Net.Sockets;

namespace Hear2Read_Voice_Manager
{
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        public MainWindow()
        {
            InitializeComponent();
            localIP = localIPAddress();

            setupDisplay();
        }
        private String[,] FilesArray = new string[20, 3];
        private int[] indexes = new int[20];
        private int numVoices = 0;
        private bool Downloading;
        private WebClient client = new WebClient();
        private String[] flitevoxFiles;
        private string langdir;
        private string voiceName;
        private string downloadFile;
        private string localIP;

        private string localIPAddress()
        {
            var request = (HttpWebRequest)WebRequest.Create("http://ifconfig.me");

            request.UserAgent = "curl"; // this will tell the server to return the information as if the request was made by the linux "curl" command

            string publicIPAddress;

            request.Method = "GET";
            using (WebResponse response = request.GetResponse())
            {
                using (var reader = new StreamReader(response.GetResponseStream()))
                {
                    publicIPAddress = reader.ReadToEnd();
                }
            }

            return publicIPAddress.Replace("\n", "");
        }
        private void Logo_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                System.Diagnostics.Process.Start("http://www.hear2read.org/");
            }
            catch { }
        }
        private void RefreshList()
        {
            //Remove currently displayed voices
            while (VoiceList.Children.Count > 0)
            {
                VoiceList.Children.RemoveAt(0);
            }
            numVoices = 0; // Clear the FilesArray
            //Re-populate list with voices
            Display_NVDA_Voices();
        }

        private void DownloadComplete(object sender, AsyncCompletedEventArgs e)
        {
            Downloading = false;
            progressBar.Value = 0;
            progressBar.Visibility = Visibility.Collapsed;
            ErrorMessage.Text = voiceName + " Added";
            RefreshList();
            // Log the download in the download 
            string httpString = "https://Hear2Read.org/nvda-addon/logDownload.php?file='" + downloadFile + "'&ip='" + localIP + "'";
            string reply = client.DownloadString(httpString);

            Downloading = false;
        }

        private void DownloadProgressChange(object sender, DownloadProgressChangedEventArgs e)
        {
            progressBar.Visibility = Visibility.Visible;
            progressBar.Value = e.ProgressPercentage;
        }

        private void Button_Click (object sender, RoutedEventArgs e)
        {
            if (Downloading) return;

            // Disable doit buttions
            ErrorMessage.Text = "";
            ErrorMessage.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF00548B"));
 
            Button button = sender as Button;
            string langdir;
            string[] tempString = button.Name.Split('_');
            int i = int.Parse(tempString[1]);
            string file = FilesArray[i, 0];
            string Action = FilesArray[i, 2];
            voiceName = FilesArray[i, 1];
            langdir = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData) + 
                                                                    "\\Hear2Read\\" + "Languages\\" + file;
            if (Action == "Remove")
            {
                // Remove the file from Hear2Read/Languages
                if (File.Exists(langdir))
                {
                    File.Delete(langdir);
                    button.Content = "Add";
                    ErrorMessage.Text = voiceName + " Removed";
                    string httpString = "https://Hear2Read.org/nvda-addon/logDownload.php?removed='" + file + "'&ip='" + localIP + "'";
                    string reply = client.DownloadString(httpString);

                }
                else
                {
                    ErrorMessage.Text = "Error Removing " + voiceName + "\n";
                    ErrorMessage.Background = new SolidColorBrush(Colors.Red);
                }
                RefreshList();
            }
            else if (Action == "Add")
            {
                // Download the file from the server
 //               button.Content = "Adding";
 //               button.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF7cfc00"));
                Downloading = true;
                Uri downloadUrl = new Uri("https://Hear2Read.org/Hear2Read/NVDA-Addon/" + file);
                downloadFile = file;
                try
                {
                    client.DownloadFileAsync(downloadUrl, langdir);
                }
                catch
                {
                    ErrorMessage.Text = "Error downloading file " + file + "\n";
                    Downloading = false;
                    RefreshList();
                    button.Content = "Add";
                    button.Foreground = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb"));
                    button.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD"));
                    return;
                }
//                StatusArray[i].Text = "Adding";
                button.Content = "Adding";
                button.Foreground = new System.Windows.Media.SolidColorBrush(Colors.LightSkyBlue);
                button.Background = new System.Windows.Media.SolidColorBrush(Colors.White);
            }
        }

        private Color SolidColorBrush(Colors colors, object red)
        {
            throw new NotImplementedException();
        }

        private void setupDisplay()
        {
            //First get a list of flitevox files 
            string reply = client.DownloadString("https://Hear2Read.org/nvda-addon/getFlitevoxNames.php");
            flitevoxFiles = reply.Split('|');

            //See if the Hear2Read/Languages directory exists, if not we know that there are no voice files loaded on this computer
            langdir = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData) + "\\Hear2Read\\";
            if (!Directory.Exists(langdir))
            {
                Directory.CreateDirectory(langdir);
            }
            langdir = langdir + "Languages\\";
            if (!Directory.Exists(langdir))
            {
                Directory.CreateDirectory(langdir);
            }

            // Make sure that the Indic_English flitevox file is installed.
            if (!File.Exists(langdir + "H2R_en_Indic-English_Male.flitevox"))
            { 
                Downloading = true;
                Uri downloadUrl = new Uri("https://Hear2Read.org/Hear2Read/NVDA-Addon/" + "H2R_en_Indic-English_Male.flitevox");
                try
                {
                    client.DownloadFile(downloadUrl, langdir + "H2R_en_Indic-English_Male.flitevox");
                }
                catch
                {
                    ErrorMessage.Text = "Error downloading file H2R_en_Indic-English_Male.flitevox\n";
                    Downloading = false;
                }
            }

            client.DownloadProgressChanged += new DownloadProgressChangedEventHandler(DownloadProgressChange);
            client.DownloadFileCompleted += new AsyncCompletedEventHandler(DownloadComplete);
            Display_NVDA_Voices();
        }

        private void Display_NVDA_Voices()
        {
            string VoiceName;
            string statusText;
            //First Create the Stackpanels to contain The voice Installed and Available Online
            StackPanel VoicesDockPanel = new StackPanel { MaxHeight = 2000, Name = "UnInstallDockPanel" };
            //Add the doit button to top of the stackpanel
            StackPanel doitpanel = new StackPanel
            {
                Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#00548B")),
                Margin = new Thickness(5, 4, 4, 4),
            };

            int index = 0;

            //Now add the Voices
            foreach (string file in flitevoxFiles)
            {
                if (file == "") continue;

                string[] bits = file.Split('_');
                if (bits.Length != 4)
                {
                    continue;
                }
                if (file == "Hear2Read voice.nvda-addon") continue;

                // Create a DocPanel for this voice
                DockPanel VoiceDockPanel = new DockPanel
                {
                    Width = 590,
                    Height = 36,
                    Margin = new Thickness(10, 0, 10, 0),
                    LastChildFill = true
                };

                if (file == "H2R_en_Indic-English_Male.flitevox")
                {
                    // Add a line for this REQUIRED voice that can not be installed or un-installed
                    voiceName = "Indic-English Male";
                    TextBlock LanguageText = new TextBlock
                    {
                        TextWrapping = TextWrapping.Wrap,
                        Margin = new Thickness(0, 0, 0, 0),
                        TextAlignment = TextAlignment.Left,
                        Width = 590,
                        Height = 36,
                        FontSize = 25,
                        Foreground = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb")),
                        Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD")),
                        Text = voiceName.PadRight(30) + "REQUIRED",
                    };
 //                   TextBlock NoActionBox = new TextBlock
 //                   {
 //                       Height = 36,
 //                       Width = 140,
 //                       Foreground = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb")),
 //                       Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD")),
 //                       Margin = new Thickness(0, 0, 0, 0),
 //                       Text = "REQUIRED",
 //                       FontSize = 25,
 //                       HorizontalAlignment = HorizontalAlignment.Center,
 //                       VerticalAlignment = VerticalAlignment.Center,
 //                  };
                    DockPanel.SetDock(LanguageText, Dock.Left);
//                    DockPanel.SetDock(StatusText, Dock.Left);
 //                   DockPanel.SetDock(NoActionBox, Dock.Right);
                    VoiceDockPanel.Children.Add(LanguageText);
//                    VoiceDockPanel.Children.Add(StatusText);
//                    VoiceDockPanel.Children.Add(NoActionBox);
                    VoicesDockPanel.Children.Add(VoiceDockPanel);

                    continue;
                }
                bits = file.Split('.');
                if ((bits.Length > 1) && (bits[1] == "exe")) continue;

                Button LanguageTextBlock = new Button
                {
                    Name = "Voice_" + index.ToString(),
                    Margin = new Thickness(0, 0, 0, 0),
                    HorizontalContentAlignment = HorizontalAlignment.Left,
                    Width = 590,
                    Height = 36,
                    FontSize = 25,
                };
//                AutomationProperties.SetName(LanguageTextBlock, Name);
                LanguageTextBlock.Click += Button_Click;
 //               Button actionButton = new Button
 //               {
 //                   Name = "Button_" + index.ToString(),
 //                   Margin = new Thickness(0, 0, 0, 0),
 //                   HorizontalContentAlignment = HorizontalAlignment.Left,
 //                   Height = 36,
 //                   Width = 140,
 //                   FontSize = 25,
 //               };
 //               actionButton.Click += Button_Click;

                FilesArray[index, 0] = file;
                bits = file.Split('_');
                string[] tempstring;
                tempstring = bits[3].Split('.');
                VoiceName = bits[2] + " " + tempstring[0];
                FilesArray[index, 1] = VoiceName;
                langdir = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData) + "\\Hear2Read\\" + "Languages\\" + file;
                if (File.Exists(langdir) == false)
                {
 //                   actionButton.Content = "Add";
                    FilesArray[index, 2] = "Add";
                    LanguageTextBlock.Content = VoiceName.PadRight(31) + "Include";
                    AutomationProperties.SetName(    LanguageTextBlock, VoiceName + ". Include");
                    AutomationProperties.SetHelpText(LanguageTextBlock, VoiceName + ". Include");
                    LanguageTextBlock.Foreground = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD"));
                    LanguageTextBlock.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb"));
 //                   actionButton.Foreground =      new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD"));
 //                   actionButton.Background =      new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb"));
                }
                else
                {
                    statusText = "Added";
//                    StatusTextBlock.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD"));
                    //                    actionCheckBox.IsChecked = false;
//                    actionButton.Background = new SolidColorBrush(Colors.Pink);
//                    actionButton.Content = "Remove";
                    FilesArray[index, 2] = "Remove";
                    LanguageTextBlock.Content += VoiceName.PadRight(31) + "Remove";
                    AutomationProperties.SetName(LanguageTextBlock, VoiceName + ". Remove");
                    AutomationProperties.SetHelpText(LanguageTextBlock, VoiceName + ". Remove");
                    LanguageTextBlock.Foreground = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb"));
                    LanguageTextBlock.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD"));
//                    actionButton.Foreground = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FF101fbb"));
//                    actionButton.Background = new System.Windows.Media.SolidColorBrush((Color)ColorConverter.ConvertFromString("#FFDDDDDD"));
                }
//                actionButton.HorizontalAlignment = HorizontalAlignment.Center;
//                actionButton.VerticalAlignment = VerticalAlignment.Center;
                //Create the textblocks which contains the Voice, Status, and desired Checkbox
                //TextWrapping = TextWrapping.Wrap,


 //               StatusTextBlock.Text = statusText;
                indexes[index] = index;

                DockPanel.SetDock(LanguageTextBlock, Dock.Left);
 //               DockPanel.SetDock(StatusTextBlock, Dock.Left);
 //               DockPanel.SetDock(actionButton, Dock.Right);
 //               actionButton.Name = "VoiceCheck" + "_" + index;
                VoiceDockPanel.Children.Add(LanguageTextBlock);
 //               VoiceDockPanel.Children.Add(StatusTextBlock);
 //               VoiceDockPanel.Children.Add(actionButton);
                VoicesDockPanel.Children.Add(VoiceDockPanel);

                numVoices += 1;
                index += 1;
            }
            index = 0;
            VoiceList.Children.Add(VoicesDockPanel);

            //Setup download events
            //            client.DownloadProgressChanged += new DownloadProgressChangedEventHandler(DownloadProgress);
        }

    }
}
