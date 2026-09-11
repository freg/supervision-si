<?php
/*
 *	@author: mOlives
 */

include_once("../tool/projeqtor.php");

if (! pq_array_key_exists('objectClass',$_REQUEST)) {
    throwError('Parameter objectClass not found in REQUEST');
}
$objectClass=$_REQUEST['objectClass'];
Security::checkValidClass($objectClass);

if (! pq_array_key_exists('objectId',$_REQUEST)) {
    throwError('Parameter objectId not found in REQUEST');
}

$objectId=$_REQUEST['objectId'];
Security::checkValidId($objectId);


$scopeClass = "LocalizationTranslatorLanguage";

$languageId=null;
if (pq_array_key_exists('languageId',$_REQUEST)) {
    $languageId=$_REQUEST['languageId'];
    Security::checkValidId($languageId);
}
$translator = new LocalizationTranslator($objectId);
$ttl = new LocalizationTranslatorLanguage($languageId);
$skillLevel = new LanguageSkillLevel();
$selectedId = $ttl->idLanguage;
$idSkillLevel = null;
$associatedLanguages = SqlList::getListWithCrit('LocalizationTranslatorLanguage', array('idTranslator'=>$translator->id), 'idLanguage');

$languages = new Language();

$allLanguagesTemp = array();
foreach (SqlList::getListWithCrit('Language', array(), 'id')as $idLanguage) {
    $allLanguagesTemp[] = $idLanguage;
}

$crit = array_diff($allLanguagesTemp, $associatedLanguages);


$critVals[] = $crit;

?>
<table>
    <tr>
        <td>
            <form id='translatorLanguageForm' name='translatorLanguageForm' onSubmit="return false;">
                <input id="translatorLanguageObjectClass" name="translatorLanguageObjectClass" type="hidden" value="<?php echo $objectClass;?>" />
                <input id="translatorLanguageObjectId" name="translatorLanguageObjectId" type="hidden" value="<?php echo $objectId;?>" />
                <input id="translatorLanguageScopeClass" name="translatorLanguageScopeClass" type="hidden" value="<?php echo $scopeClass;?>" />
                <input id="translatorLanguageSelectedId" name="translatorLanguageSelectedId" type="hidden" value="<?php echo $languageId;?>" />

                <table>
                    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
                    <tr><td colspan="2" class="section"><?php echo i18n('sectionProductLanguage',array(i18n($objectClass),intval($objectId)));?></td></tr>
                    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
                    <tr>
                        <td class="dialogLabel">
                            <label for="translatorLanguageName" ><?php echo i18n('Language'); ?>&nbsp;:&nbsp;</label>
                        </td>
                        <td>
                            <select size="8" id="translatorLanguageListId" name="translatorLanguageListId[]"
                                onchange="if (this.value && dijit.byId('translatorLanguageSkillLevelId').value > 0) enableWidget('dialogTranslatorLanguageSubmit');"
                                <?php if (!$languageId) echo 'multiple'; ?> class="selectList"  value="">
                                <?php htmlDrawOptionForReference('idLanguage', $selectedId, $ttl, true, "id",$critVals);?>
                            </select>
                        </td>
                    </tr>
                    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>

                    <tr>
                        <td class="dialogLabel">
                            <label for="translatorLanguageSkillLevelId" ><?php echo i18n('skillLevels'); ?>&nbsp;:&nbsp;</label>
                        </td>
                        <td>
                            <select dojoType="dijit.form.FilteringSelect"
                                    <?php echo autoOpenFilteringSelect();?>
                                    id="translatorLanguageSkillLevelId" name="translatorLanguageSkillLevelId"
                                    missingMessage="<?php echo i18n('messageMandatory',array(i18n('languageSkillLevelValues')));?>"
                                    class="input required" value="" >
                                <?php htmlDrawOptionForReference('idLanguageSkillLevel', $idSkillLevel, null, true);?>
                                <script type="dojo/connect" event="onChange" args="evt" >
                                    if(document.getElementById("translatorLanguageListId").selectedIndex >= 0){
                                        enableWidget('dialogTranslatorLanguageSubmit');
                                    }
                                </script>
                            </select>
                        </td>
                    </tr>
                    <tr><td>&nbsp;</td><td>&nbsp;</td></tr>
                </table>
            </form>
        </td>
    </tr>
    <tr>
        <td align="center">
            <button class="mediumTextButton" dojoType="dijit.form.Button" type="button" onclick="dijit.byId('dialogTranslatorLanguage').hide();">
                <?php echo i18n("buttonCancel");?>
            </button>
            <button class="mediumTextButton" disabled dojoType="dijit.form.Button" type="submit" id="dialogTranslatorLanguageSubmit" onclick="protectDblClick(this);saveTranslationLanguage();return false;">
                <?php echo i18n("buttonOK");?>
            </button>
        </td>
    </tr>
</table>
