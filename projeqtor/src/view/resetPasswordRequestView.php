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

/* ============================================================================
 * Connnexion page of application.
 */
define('ANONYMOUS_ACCESS', true);
require_once "../tool/projeqtor.php";
header ('Content-Type: text/html; charset=UTF-8');
scriptLog('   ->/view/resetPasswordRequestView.php');

$mobile=false;
setSessionValue('resetPasswordChangeInProgress', 'true');

$resetEnabled = (Parameter::getGlobalParameter('passwordResetEnabled','NO')=='YES');
if (! $resetEnabled) {
  echo i18n('errorResetPasswordNotEnabled');
  exit;
}

$token = RequestHandler::getValue('token');
if ($token) {
  setSessionValue('passwordResetToken', $token);
}
$currentLocale = getSessionValue('currentLocale');
if (! $currentLocale) $currentLocale = Parameter::getGlobalParameter('defaultLocale');
?>
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="content-type" content="text/html; charset=UTF-8" />
  <?php Security::writeMetaCSP();?>
<?php if (! isset($debugIEcompatibility) or $debugIEcompatibility==false) {?>  
  <meta http-equiv="X-UA-Compatible" content="IE=edge" />
<?php }?> 
  <title><?php echo i18n("applicationTitle");?></title>
  <link rel="shortcut icon" href="img/logo.ico" type="image/x-icon" />
  <link rel="icon" href="img/logo.ico" type="image/x-icon" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtor.css');?>" />
  <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('css/projeqtorFlat.css');?>" />
    <?php if(isNewGui()){?>
   <link rel="stylesheet" type="text/css" href="<?php echoStaticFileNameWithCacheMgt('../view/css/projeqtorNew.css');?>" />
   <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/dynamicCss.js');?>" ></script>
   <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorNewGui.js');?>" ></script>
   <?php }?>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/CryptoJS/rollups/sha256.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtor.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialog.js');?>" ></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('js/projeqtorDialogAlertNotification.js');?>"></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/dojo.js');?>"
    djConfig='modulePaths: {"i18n":"../../tool/i18n",
                            "i18nCustom":"../../plugin"},
              parseOnLoad: true, 
              isDebug: <?php echo getBooleanValueAsString(Parameter::getGlobalParameter('paramDebugMode'));?>'></script>
  <script type="text/javascript" src="<?php echoStaticFileNameWithCacheMgt('../external/dojo/projeqtorDojo.js');?>"></script>
  <script type="text/javascript"> 
    var isNewGui=<?php echo (isNewGui())?'true':'false';?>;
    var customMessageExists=<?php echo(file_exists(Plugin::getDir()."/nls/$currentLocale/lang.js"))?'true':'false';?>;
    dojo.require("dojo.parser");
    dojo.require("dojo.i18n");
    dojo.require("dijit.Dialog"); 
    dojo.require("dijit.form.ValidationTextBox");
    dojo.require("dijit.form.TextBox");
    dojo.require("dijit.form.Button");
    dojo.require("dijit.form.Form");
    dojo.require("dijit.form.FilteringSelect");
    dojo.require("dojox.form.PasswordValidator");
    var fadeLoading=<?php echo getBooleanValueAsString(Parameter::getGlobalParameter('paramFadeLoadingMode'));?>;
    dojo.addOnLoad(function(){
      if (isNewGui) {
        changeTheme('<?php echo getTheme();?>');
        setColorTheming('<?php echo '#'.Parameter::getUserParameter('newGuiThemeColor');?>','<?php echo '#'.Parameter::getUserParameter('newGuiThemeColorBis');?>');
      }
      currentLocale="<?php echo $currentLocale?>";
      hideWait();
      resetPasswordChange=false;
    }); 
  </script>
</head>

<?php 
if(isNewGui()){
$firstColor=Parameter::getUserParameter('newGuiThemeColor');
if(!$firstColor){
$firstColor= getTheme();
}
?>
<body id="body" class="nonMobile tundra <?php echo getTheme();?>" style="overflow: auto;<?php if (isNewGui()) echo 'background-color:#'.$firstColor.' !important;';?>">
<?php 
}else{
?>
<body class="<?php echo getTheme();?>"  >
<?php }?>
  <div id="wait" >
  </div> 
  <?php if (!isFF() and isNewGui()) echo '<div style="position:absolute;margin-top:-50%;margin-left:-0%;width:250%;height:250%;opacity:0.1 !important;z-index:-2;" class="loginBackgroundNewGui"></div>';?>
  <?php if (isFF() and isNewGui()) echo '<div style="position:absolute;margin-top:-40%;margin-left:-10%;width:250%;height:250%;z-index:-2;"><img style="width:100%;height:100%;opacity:0.1 !important" src="css/images/Engrenages.svg" /></div>';?>
  <?php if (isNewGui()) echo '<div style="position:absolute;width:100%;height:100%;opacity:0.6 !important;z-index:-1;" class="loginBackgroundNewGui"></div>';?>
  <table align="center" width="100%" height="100%" class="<?php echo (isNewGui())?'':'loginBackground';?>" >
    <tr height="100%">
      <td width="100%" align="center">
        <div class="background  <?php  echo (isNewGui())?'loginFrameNewGui':'loginFrame' ;?>" style="<?php if (SSO::isEnabled()) { echo 'height:450px';}else{ echo 'height:auto';}?>" >
        <table  align="center" >
		    <?php if(isNewGui()){?>
			    <tr style="height:42px;" >
			     <td align="center" style="position:relative;height: 1%;" valign="center">
			       <div style="position:relative;height:75px;">
			         <div class="divLoginIconDrawing" style="position:absolute;background-color:#<?php echo $firstColor;?>";>
			           	<div class="divLoginIconBig"></div>		         
			         </div>
			       </div>
			     </td>
			    </tr>
	    <?php }?>
          <tr style="height:10px;" >
  	        <td align="left" style="position:relative;height: 1%;" valign="top">
  	          <div style="position:relative;width: 400px; height: 54px;">
  	            <div style="z-index:10;overflow:visible;position:absolute;width: 480px; height: 50px;top:15px;text-align: center">
  		           <img style="max-height:60px" src="<?php 
    		          if (file_exists("../logo.gif")) echo '../logo.gif';
    		          else if (file_exists("../logo.jpg")) echo '../logo.jpg';
    		          else if (file_exists("../logo.png")) echo '../logo.png';
    		          else echo '../view/img/titleSmall.png';?>" />
  	            </div>
  	          </div>
            </td>
  	      </tr>
          <tr style="height:100%" height="100%">
            <td style="height:99%" align="left" valign="middle">
              <div  id="formDiv" dojoType="dijit.layout.ContentPane" region="center"style="background:transparent !important;width: 470px; overflow:hidden;position: relative;">
             <form  dojoType="dijit.form.Form" id="resetPasswordForm" jsId="resetPasswordForm" name="resetPasswordForm" encType="multipart/form-data" action="" method="" style="padding-bottom: 5px;">
             <script type="dojo/method" event="onSubmit" >
              return false;       
            </script>
            <?php 
            $topMsg=230;
            if(!isNewGui())echo '<br/>'?>
            <br/><br/>
            <div id="onlyMessageDiv" style="display:none;width:470px;margin:15 auto;text-align:center;">
  							<div id="onlyMessageContent"></div>
            </div>
            <div class="input rounded" id="contentFormDiv" style="color:#000000;<?php echo (isNewGui())?'border:unset !important;width:440px;':'padding:10px;margin-left:15px;';?>">
              <?php
              if (isNewGui()) echo '<div class="loginDivContainer container" style="margin-bottom:15px;">';?>
              <label for="login" class="label" style="<?php echo (isNewGui())?"position: relative;text-align:center;width:100px;margin-top: 4px;":"width:150px;";?>;"><?php echo i18n('login');?>&nbsp;:&nbsp;</label>
              <div type="text" dojoType="dijit.form.ValidationTextBox" name="login" id="login" required="true" trim="true"
                  style="width:310px;" class="input" value=""></div><br/>
              <?php if (isNewGui()){
                echo '</div>';
              }else{?>
              <br/>
              <?php
              }
               if(isNewGui())echo '<div class="loginDivContainer container" ><div style="float:left">'; ?>
              <label for="resetEmail" class="label" style="<?php echo (isNewGui())?"position: relative;text-align:center;width:100px;margin-top: 4px;":"width:150px;";?>"><?php echo i18n('displayMail');?>&nbsp;:&nbsp;</label>
              <div type="text" dojoType="dijit.form.ValidationTextBox" name="email" id="email" required="true" trim="true" invalidMessage="<?php echo i18n('invalidEmail'); ?>" regExp="^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                  style="width:310px;" class="input" value=""></div><br/>
              <?php if(isNewGui()){
                 echo  '</div>';
               }?>
            </div>
            <br/>
            <table><tr>
            <td>
              <button  class="largeTextButton" type="button" style="margin-left:80px;width:150px !important;float:left;height:20px !important;width:200px;color:#555555;" id="cancelButton" dojoType="dijit.form.Button" showlabel="true"><?php echo i18n('buttonCancel');?>
                <script type="dojo/connect" event="onClick" args="evt">
                  showWait(); 
                  window.location=".";
                </script>
              </button>
              </td>
              <td>
              <button class="largeTextButton" type="submit" style="margin-right:80px;width:150px !important;float:right;height:20px !important;width:200px;color:#555555;" id="buttonLoginPwChange" dojoType="dijit.form.Button" showlabel="true"><?php echo ucfirst(i18n('send'));?>
                <script type="dojo/connect" event="onClick" args="evt">
                  sendRequestResetPassword();
                </script>
              </button>
              </td>
            </tr></table>    
            <br/>
            <div id="passwordResultDiv" dojoType="dijit.layout.ContentPane" region="none" style="overflow:visible;top:<?php echo $topMsg;?>px;"></div>
            </form>
            </div>
            </td>
          </tr>
        </table>
        </div>
      </td>
    </tr>
  </table>
  <div id="dialogAlert" dojoType="dijit.Dialog" title="<?php echo i18n("dialogAlert");?>">
      <table>
        <tr>
          <td width="50px">
               <?php echo formatIcon('Alert', 32);?>
          </td>
          <td>
            <div id="dialogAlertMessage">
            </div>
          </td>
        </tr>
        <tr><td colspan="2" align="center">&nbsp;</td></tr>
        <tr>
          <td colspan="2" align="center">
            <button class="smallTextButton" dojoType="dijit.form.Button" type="submit" onclick="dijit.byId('dialogAlert').acceptCallback();dijit.byId('dialogAlert').hide();">
              <?php echo i18n("buttonOK");?>
            </button>
          </td>
        </tr>
      </table>
    </div>
</body>
</html>
