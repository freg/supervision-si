<?php
/*
 * @author : mOlives
 */
require_once "../tool/projeqtor.php";


$objectClass=RequestHandler::getClass('translatorLanguageObjectClass',true);
$objectId=RequestHandler::getId('translatorLanguageObjectId',true);
$listId=RequestHandler::getValue('translatorLanguageListId',true);
$TranslatorLanguageClass=RequestHandler::getClass('translatorLanguageScopeClass',true);
$idLevelSKill = RequestHandler::getValue('translatorLanguageSkillLevelId',true);
$selectedId =  RequestHandler::getValue('translatorLanguageSelectedId',true);
Sql::beginTransaction();
$result="";

foreach ($listId as $id) {

    $ttl = new LocalizationTranslatorLanguage($selectedId); // if selected then update, else $selectedId is null then create new object
    $ttl->idTranslator = $objectId;
    $ttl->idLanguage = $id;
    $ttl->idLanguageSkillLevel = $idLevelSKill;
    $ttl->idUser = getSessionUser()->id;
    $ttl->creationDate = date('Y-m-d');
    $ttl->idle = 0;
    $res = $ttl->save();
    if (!$result) {
        $result=$res;
    } else if (pq_stripos($res,'id="lastOperationStatus" value="OK"')>0 ) {
        if (pq_stripos($result,'id="lastOperationStatus" value="OK"')>0 ) {
            $deb=pq_stripos($res,'#');
            $fin=pq_stripos($res,' ',$deb);
            $resId=pq_substr($res,$deb, $fin-$deb);
            $deb=pq_stripos($result,'#');
            $fin=pq_stripos($result,' ',$deb);
            $result=pq_substr($result, 0, $fin).','.$resId.pq_substr($result,$fin);
        } else {
            $result=$res;
        }
    }

}

displayLastOperationStatus($result);



