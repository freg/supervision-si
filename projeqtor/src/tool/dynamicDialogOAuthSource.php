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

require_once "../tool/projeqtor.php";
$idOAuth=RequestHandler::getId('idOAuth');
$oauth=new OAuthClient($idOAuth);

if (! $oauth->scope) $oauth->scope=$oauth->getScope();
$url=$oauth->getAccesUrl();
?>
<table>
  <tr>
    <td>
      <form id='oauthManagement' name='oauthManagement' onSubmit="return false;">
      	<input id="idOAuthClient" name="idOAuthClient" type="hidden" value="<?php echo $oauth->id;?>" />
        <table>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr><td colspan="2" class="section"><?php echo i18n('colDescription');?></td></tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>  
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthName" ><?php echo i18n('colName'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:250px;"dojoType="dijit.form.TextBox"  size="100" id="dialogOAuthName" name="dialogOAuthName" value="<?php echo $oauth->name;?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthSourceId" ><?php echo i18n('colOAuthSource'); ?>&nbsp;&nbsp;</label></td>
            <td>
            	<?php $sources=array('office365'=>'Microsoft Office 365','office'=>'Microsoft Office','graph'=>'Microsoft Graph');?>
    	        <select dojoType="dijit.form.FilteringSelect" class="input" id="dialogOAuthSourceId" name="dialogOAuthSourceId" 
    	          <?php echo autoOpenFilteringSelect();?> style="width:120px;height:20px">
                <?php 
                foreach ($sources as $sourceId=>$sourceName) {
                  $select=($oauth->oauthSource==$sourceId)?' selected ':'';
                  echo "<option value='$sourceId' $select >$sourceName</option>";
                }?>
              </select>
             </td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthTenantId" ><?php echo i18n('colOAuthTenantID'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  size="200" id="dialogOAuthTenantId" name="dialogOAuthTenantId" value="<?php echo $oauth->tenantId;?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthClientId" ><?php echo i18n('colOAuthClientID'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  size="2000" id="dialogOAuthClientId" name="dialogOAuthClientId" value="<?php echo $oauth->clientId;?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthClientSecret" ><?php echo i18n('colOAuthClientSecret'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox" type="password" size="2000" id="dialogOAuthClientSecret" name="dialogOAuthClientSecret" value="<?php echo $oauth->getSecret();?>"  /></td>
          </tr>
          <tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthRedirectUri" ><?php echo i18n('colOAuthRedirectUri'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  readonly size="2000" id="dialogOAuthRedirectUri" name="dialogOAuthRedirectUri" value="<?php echo $oauth->getRedirectUri();?>"  /></td>
          </tr>
          <tr>
           <td></td>
           <td>
             <button class="dynamicTextButton" dojoType="dijit.form.Button" type="button" 
               onclick="protectDblClick(this);getOauthToken();"><?php echo i18n("getToken");?>
             </button>
           </td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
          <tr><td colspan="2" class="section"><?php echo "token";//i18n('colToken');?></td></tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>  
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthScope" ><?php echo 'scope';//i18n('colOAuthScope'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  readonly size="4000" id="dialogOAuthScope" name="dialogOAuthScope" value="<?php echo $oauth->scope;?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthUri" ><?php echo 'URL';//i18n('colUrl'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  readonly size="4000" id="dialogOAuthUri" name="dialogOAuthUri" value="<?php echo $url;?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="" ><?php echo 'token';//i18n('colUrl'); ?>&nbsp;&nbsp;</label></td>       
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  readonly size="2000" value="<?php echo $oauth->getTokenLabel();?>"  /></td>
            
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthRefreshToken" ><?php echo 'refresh token';//i18n('colUrl'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  readonly size="2000" id="100" name="dialogOAuthRefreshToken" value="<?php echo $oauth->getRefreshTokenLabel();?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="dialogOAuthTokenDateTime" ><?php echo 'token date';//i18n('colUrl'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:150px;"dojoType="dijit.form.TextBox"  readonly size="20" id="dialogOAuthTokenDateTime" name="dialogOAuthTokenDateTime" value="<?php echo $oauth->tokenDateTime;?>"  /></td>
          </tr>
          <tr>
            <td class="dialogLabel"  ><label for="" ><?php echo 'token expires';//i18n('colUrl'); ?>&nbsp;&nbsp;</label></td>
            <td><input style="width:500px;"dojoType="dijit.form.TextBox"  readonly size="100" value="<?php echo $oauth->getExpiresLabel();?>"  /></td>
          </tr>
          <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
        </table>
      </form>
    </td>
  </tr>
  <tr>
    <td align="center">
      <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogOAuthSource').hide();">
        <?php echo i18n("buttonCancel");?>
      </button>
      <button class="mediumTextButton" dojoType="dijit.form.Button" type="submit" id="dialogOAuthSourceSubmit" onclick="protectDblClick(this);saveOAuth();return false;">
        <?php echo i18n("buttonOK");?>
      </button>
    </td>
  </tr>
</table>