<?php
/*
 * 	@author: mOlives
 */
require_once "../tool/projeqtor.php";

$translatorLanguageId=pq_trim(RequestHandler::getId('translatorLanguageId',true));
$refType=RequestHandler::getClass('refType',true);

Sql::beginTransaction();
$result='';

$obj=new LocalizationTranslatorLanguage($translatorLanguageId);
$result=$obj->delete();

// Message of correct saving
displayLastOperationStatus($result);