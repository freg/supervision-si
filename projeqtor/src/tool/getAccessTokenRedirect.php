<?php
/*** COPYRIGHT NOTICE *********************************************************
 *
 * Copyright 2009-2017 ProjeQtOr - Pascal BERNARD - support@projeqtor.org
 * Contributors : -
 *
 * This file is part of ProjeQtOr.
 * 
 * ProjeQtOr is free software: you can redistribute it and/or modify it under 
 * the terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) 
 * any later version.
 * 
 * ProjeQtOr is distributed in the hope that it will be useful, but WITHOUT ANY
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
 * FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for 
 * more details.
 *
 * You should have received a copy of the GNU Affero General Public License along with
 * ProjeQtOr. If not, see <http://www.gnu.org/licenses/>.
 *
 * You can get complete code of ProjeQtOr, other resource, help and information
 * about contributors at http://www.projeqtor.org 
 *     
 *** DO NOT REMOVE THIS NOTICE ************************************************/

/** ===========================================================================
 * Save filter from User to Session to be able to restore it
 * Retores it if cancel is set
 * Cleans it if clean is set
 * The new values are fetched in $_REQUEST
 */

require_once "../tool/projeqtor.php";
$oauth=getSessionValue('OAUTH2');
$message="";
$result="OK";
$colorMessage='#5555AA';

if ($oauth) {
  $returnValue=$oauth->initializeToken();
  $result=$returnValue['result'];
  $message=$returnValue['message'];
} else {
  $result="ERROR";
  errorLog("OAUTH2 REDIRECTION ERROR");
  errorLog("  'OAUTH2' not found in session");
  errorLog("  ===== REQUEST");
  errorLog($_REQUEST);
  errorLog("  ===== SESSION");
  errorLog($_SESSION);
  errorLog("  ===== ");
  $message="OAUTH2 REDIRECTION ERROR";
}
if ($result=='ERROR') {
  $message.="<br/> <i>detail can be found in log file</i>";
  $colorMessage='#AA5555';
}
$logo="../view/img/title.png";
if (file_exists("../logo.gif")) $logo="../logo.gif";
if (file_exists("../logo.png")) $logo="../logo.png";
?>
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
  </head>
  <body style="width:100%;height:100%;overflow:hidden">
    <div style="width:100%;height:100%;">
      <table style="width:100%;height:100%;">
        <tbody>
          <tr style="height:100%; vertical_align: middle;">
            <td style="width:100%;text-align: center;position:relative">
              <div style="position:relative;width:100%;height:100%;left:0px;">        
                <div style="position:relative;width:100%;height:100%; top:200px;">
                  <img style="height:50%;top:25%;left:25%;opacity:0.10;filter:alpha(opacity=10);" src="../view/img/logoBig.png">
                </div>
                <div style="position:absolute;height:100%;top:5%;right:5%;">
                  <img style="max-height:60px" src="<?php echo $logo;?>"/>
                </div>
              </div>
              <div style="font-family:verdana, arial;font-size:150%;font-weight:bold;color:#A0A0A0; position:fixed;bottom:50%;left:0;width:100%;text-align:center;">
                Vous pouvez maintenant fermer la fenêtre
              </div>
              <div style="position:absolute; height:25%; min-height:200px; top:5%; left:25%; width:50%; min-width:500px; font-family:verdana, arial; font-size:200%; color:<?php echo $colorMessage;?>">
                <?php echo $message; ?>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </body>
</html>