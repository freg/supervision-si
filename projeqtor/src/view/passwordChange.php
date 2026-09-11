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
   require_once "../tool/projeqtor.php";
   header ('Content-Type: text/html; charset=UTF-8');
   scriptLog('   ->/view/passwordChange.php'); 
   $mobile=false;
   setSessionValue('passwordChangeInProgress', 'true');
   if(getSessionValue('Token')==''){
     $token=bin2hex(random_bytes(35));
     setSessionValue('Token', $token);
   }else{
     $token=getSessionValue('Token');
   }
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
    var csrfToken='<?php echo $token?>';
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
      changePassword=false;
      if (dojo.byId('dojox_form__NewPWBox_0') && dojo.byId('oldPwd') == undefined) dojo.byId('dojox_form__NewPWBox_0').focus();
      if (dojo.byId('oldPwd')) dojo.byId('oldPwd').focus();
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
             <form  dojoType="dijit.form.Form" id="passwordForm" jsId="passwordForm" name="passwordForm" encType="multipart/form-data" action="" method="" style="padding-bottom: 5px;">
             <script type="dojo/method" event="onSubmit" >
              if (dojo.byId('goButton')) dojo.byId('goButton').focus();
              var extDate=new Date();
              var userSalt=CryptoJS.SHA256('projeqtor'+extDate.getTime());
              dojo.byId('userSalt').value=userSalt;
              var pwd=dijit.byId('password').get('value')+userSalt;
              var crypted=CryptoJS.SHA256(pwd);
              dojo.byId('hashString').value=crypted;
              dojo.byId('passwordLength').value=dijit.byId('password').get('value').length;
              <?php if(Parameter::getGlobalParameter('requiredOldPassword') == 'YES' and getSessionUser()->crypto == 'sha256'){?>
              var oldUserSalt=dojo.byId('oldUserSalt').value;
              var oldPwd=dojo.byId('oldPwd').value+oldUserSalt;
              var oldCrypted=CryptoJS.SHA256(oldPwd);
              dojo.byId('oldHashString').value=oldCrypted;
              <?php } ?>
              <?php if(Parameter::getGlobalParameter('oldPasswordDifferentNew') == 'YES' and getSessionUser()->crypto == 'sha256'){?>
              var oldUserSalt=dojo.byId('oldUserSalt').value;
              var newPwdOldSalt= dojo.byId('password').value+oldUserSalt;
              var newCryptedOldSalt=CryptoJS.SHA256(newPwdOldSalt);
              dojo.byId('newPasswordWithOldSalt').value=newCryptedOldSalt;
              <?php } ?>
              loadContent("../tool/changePassword.php","passwordResultDiv", "passwordForm");
              return false;       
            </script>
            <?php
            $topMsg=230;
            if (isset($ssoUserCreated) and $ssoUserCreated==true) {
            	echo '<b>'.i18n('newUserSSO').'</b><br/>'; 
            	$topMsg+=20;
            }
            if (SSO::isEnabled()) {
            	echo '<div style="padding-top:20px">'.i18n('ssoChangePasswordMessage',array(SSO::getCommonName())).'</div>';
            	$topMsg+=40;
            }
            ?> 
            <?php if(!isNewGui())echo '<br/>'?>
            <br/>
            <?php if(Parameter::getGlobalParameter('requiredOldPassword') == 'YES' and getSessionUser()->crypto == 'sha256'){?>
                <?php if (isNewGui()) echo '<div class="loginDivContainer container" style="height:auto;width:450px;margin-bottom:15px;">';?>
                <label class="label" style="<?php echo (isNewGui())?"position: relative;text-align:center;width:180px;margin-top: 4px;":"width:150px;";?>;"><?php echo i18n('oldPassword');?>&nbsp;:&nbsp;</label>
                <input id="oldPwd" type="password"  dojoType="dijit.form.ValidationTextBox"  class="input rounded"  style="color:#000000;width:200px">
                <?php if (isNewGui()){
                  echo '<div class="iconView imageColorNewGui iconSize22" style="cursor:pointer;float:right;position:relative;top:8px;margin-right:8px;"
                       onClick="changePasswordType(true);" ></div>';
                  echo '</div>';
                }else{?>
                <br/>
                <?php
                }
              }?>
            <div dojoType="dojox.form.PasswordValidator" id="password" onkeydown="setTimeout('controlChar();',20);" class="input rounded"  style="color:#000000;<?php echo (isNewGui())?'border:unset !important;width:440px;':'padding:10px;margin-left:15px;';?>">
              <?php
              if (isNewGui()) echo '<div class="loginDivContainer container" style="margin-bottom:15px;">';?>
              <label class="label" style="<?php echo (isNewGui())?"position: relative;text-align:center;width:180px;margin-top: 4px;":"width:150px;";?>;"><?php echo i18n('newPassword');?>&nbsp;:&nbsp;</label>
              <input type="password" pwType="new" class="input rounded"  style="color:#000000;"><br/>
              <?php if (isNewGui()){
                echo '</div>';
              }else{?>
              <br/>
              <?php
              }
               if(isNewGui())echo '<div class="loginDivContainer container" ><div style="float:left">'; ?>
              <label class="label" style="<?php echo (isNewGui())?"position: relative;text-align:center;width:180px;margin-top: 4px;":"width:150px;";?>"><?php echo i18n('validatePassword');?>&nbsp;:&nbsp;</label>
              <input type="password" pwType="verify" class="input rounded"  style="color:#000000;">
              <?php if(isNewGui()){
                 echo  '</div>';
                 echo '<div class="iconView imageColorNewGui iconSize22" style="cursor:pointer;float:right;position:relative;top:8px;margin-right:8px;" 
                       onClick="changePasswordType();" ></div>';
                 echo '</div>';
               }?>
              <br/>
              <?php if(!isNewGui())echo '<br/>'?>
              <p><progress  id="progress" max="4" style="margin-left:<?php echo (isNewGui())?'145px':'148px';?>;width:185px;" value="0" ></progress> <span id="error" style="float:right;" ></span></p>
              <div style="width:200px;height:20px; <?php echo (isNewGui())?'position: relative;top:8px;left:135px;fonr-size:12px;white-space: nowrap;':'position:absolute; left:170px;';?>text-align:center;">
                <span id="strength"></span> 
              </div>
            <br/>
            <!-- florent 4088 -->
            </div>
            <input type="hidden" id="parmPwdSth"  value="<?php echo Parameter::getGlobalParameter('paramPasswordStrength');?>"/>
            <input type="hidden" id="paramPwdLth"  value="<?php echo Parameter::getGlobalParameter('paramPasswordMinLength');?>"/>
            <input type="hidden" id="hashString" name="password" value=""/>
            <input type="hidden" id="userSalt" name="userSalt" value=""/>
            <input type="hidden" id="passwordLength" name="passwordLength" value=""/>
            <input type="hidden" id="passwordValidate" name="passwordValidate" value=""/>
            <input type="hidden" id="criteria" name="criteria" value=""/>
            <?php if(Parameter::getGlobalParameter('requiredOldPassword') == 'YES' and getSessionUser()->crypto == 'sha256'){?>
            <input type="hidden" id="oldHashString" name="oldPassword" value=""/>
            <input type="hidden" id="oldUserSalt" name="oldUserSalt" value="<?php echo getSessionUser()->salt;?>"/>
            <?php }?>
            <?php if(Parameter::getGlobalParameter('oldPasswordDifferentNew') == 'YES' and getSessionUser()->crypto == 'sha256'){?>
            <input type="hidden" id="oldHashString" name="oldPassword" value=""/>
            <input type="hidden" id="oldUserSalt" name="oldUserSalt" value="<?php echo getSessionUser()->salt;?>"/>
            <input type="hidden" id="newPasswordWithOldSalt" name="newPasswordWithOldSalt" value="xxx"/>
            <?php }?>
            <!-- florent -->
            <?php if(!isNewGui()){ ?>
            <br/>
            <button id="buttonLoginPwChange" type="submit" style="margin-left:150px;';width:200px;color:#555555;" class="largeTextButton" id="goButton" dojoType="dijit.form.Button" showlabel="true"><?php echo i18n('loginLib');?>
              <script type="dojo/connect" event="onClick" args="evt">
                //loadContent("../tool/changePassword.php","passwordResultDiv", "passwordForm");
              </script>
            </button>
            <br/>
            <div style="height:5px">&nbsp;</div>
            <?php if ( $user->password != md5($user->getRandomPassword()) ) {?>
            <button  class="largeTextButton" type="button" style="margin-left:150px;';width:200px;color:#555555;" id="cancelButton" dojoType="dijit.form.Button" showlabel="true"><?php echo i18n('buttonCancel');?>
              <script type="dojo/connect" event="onClick" args="evt">
              showWait(); 
              window.location=".";
              </script>
            </button>  
            <?php } }else{?>
            <?php if ( $user->password != md5($user->getRandomPassword()) ) {?>
            <button  class="largeTextButton" type="button" style="margin-left:80px;width:150px !important;float:left;height:20px !important;width:200px;color:#555555;" id="cancelButton" dojoType="dijit.form.Button" showlabel="true"><?php echo i18n('buttonCancel');?>
              <script type="dojo/connect" event="onClick" args="evt">
              showWait(); 
              window.location=".";
              </script>
            </button>
            <button id="buttonLoginPwChange" type="submit" style="margin-right:80px;width:150px!important;;height:20px !important;float:right;width:200px;color:#555555;" class="largeTextButton" id="goButton" dojoType="dijit.form.Button" showlabel="true"><?php echo i18n('passwordLib');?>
              <script type="dojo/connect" event="onClick" args="evt">
                //loadContent("../tool/changePassword.php","passwordResultDiv", "passwordForm");
              </script>
            </button>    
            <?php } }?>
            <br/><br/>
            <div id="passwordResultDiv" dojoType="dijit.layout.ContentPane" region="none" style="overflow:visible;top:<?php echo $topMsg;?>px;">
            </div>
            </form>
            </div>
     
            </td>
          </tr>
        </table>
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
